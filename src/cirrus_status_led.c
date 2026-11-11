/*
 * Cirrus status light: one side-facing RGB LED on the left half.
 *
 * What it shows, most important first:
 *   1. Short signals, played one after another (they never cut each other off):
 *        - Bluetooth profile switch: blue blinks, 1 blink = profile 1, 2 = profile 2, ...
 *        - Power-on / wake: 1 s battery check (green > 50%, yellow, red = low)
 *        - Low battery, every 30 s while typing: left half = 1 red blink,
 *          right half = 2 fast red blinks
 *   2. The highest active layer that has a color (Layer Lock, System, Nav, Numpad, ...)
 *   3. Caps Lock
 *   4. "Below Caps Lock" layers (word-delete mode)
 * When there is nothing to show, the LED's power is switched off completely.
 *
 * Colors and brightness are set in config/boards/shields/cirrus/cirrus_left.overlay.
 * Property descriptions: dts/bindings/zmk,cirrus-status-led.yaml
 */

#define DT_DRV_COMPAT zmk_cirrus_status_led

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/led_strip.h>
#include <zephyr/init.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <zmk/activity.h>
#include <zmk/event_manager.h>
#include <zmk/events/activity_state_changed.h>
#include <zmk/events/hid_indicators_changed.h>
#include <zmk/events/layer_state_changed.h>
#include <zmk/keymap.h>

#if IS_ENABLED(CONFIG_ZMK_BATTERY_REPORTING)
#include <zmk/battery.h>
#include <zmk/events/battery_state_changed.h>
#endif
#if IS_ENABLED(CONFIG_ZMK_BLE)
#include <zmk/events/ble_active_profile_changed.h>
#endif

LOG_MODULE_REGISTER(cirrus_status_led, CONFIG_ZMK_LOG_LEVEL);

/* ---------- settings from the devicetree (cirrus_left.overlay) ---------- */

static const struct device *const strip = DEVICE_DT_GET(DT_INST_PHANDLE(0, led_strip));

#if DT_INST_NODE_HAS_PROP(0, power_gpios)
#define HAS_POWER_PIN 1
static const struct gpio_dt_spec power_pin = GPIO_DT_SPEC_INST_GET(0, power_gpios);
#else
#define HAS_POWER_PIN 0
#endif

#if DT_INST_NODE_HAS_PROP(0, layer_colors)
static const uint32_t layer_colors[] = DT_INST_PROP(0, layer_colors);
#define NUM_LAYER_COLORS ARRAY_SIZE(layer_colors)
#else
static const uint32_t layer_colors[] = {0};
#define NUM_LAYER_COLORS 0
#endif

#if DT_INST_NODE_HAS_PROP(0, below_caps_layers)
static const uint8_t below_caps_layers[] = DT_INST_PROP(0, below_caps_layers);
#define NUM_BELOW_CAPS ARRAY_SIZE(below_caps_layers)
#else
static const uint8_t below_caps_layers[] = {0};
#define NUM_BELOW_CAPS 0
#endif

#define BRIGHTNESS DT_INST_PROP(0, brightness)
#define CAPS_COLOR DT_INST_PROP(0, caps_lock_color)
#define BT_COLOR DT_INST_PROP(0, bt_profile_color)
#define BATT_GOOD_COLOR DT_INST_PROP(0, battery_good_color)
#define BATT_MEDIUM_COLOR DT_INST_PROP(0, battery_medium_color)
#define LOW_BATT_PERCENT DT_INST_PROP(0, low_battery_percent)
#define LOW_BATT_COLOR DT_INST_PROP(0, low_battery_color)
#define IDLE_OFF DT_INST_PROP(0, idle_off)

#define HID_CAPS_LOCK_BIT BIT(1) /* HID LED usage 0x02; bit 0 is Num Lock */

/* ---------- timing ---------- */

#define REMINDER_PERIOD_MS 30000 /* low-battery reminder interval */
#define GAP_MS 300               /* dark pause after every signal so back-to-back ones stay distinct */
#define BLINK_MS 150             /* Bluetooth profile blinks */
#define FAST_BLINK_MS 100        /* right-half low-battery blinks */
#define BOOT_QUIET_MS 3000       /* ignore the profile "switch" that happens while starting up */

/* ---------- short signals and their queue ---------- */

#define MAX_STEPS 12
#define QUEUE_LEN 6

enum signal_kind { SIG_BT_PROFILE, SIG_BATTERY_CHECK, SIG_LOW_LEFT, SIG_LOW_RIGHT };

struct step {
    uint32_t color; /* 0 = dark */
    uint16_t ms;
};

struct signal {
    enum signal_kind kind;
    uint8_t n_steps;
    struct step steps[MAX_STEPS];
};

static const struct signal low_left_signal = {
    .kind = SIG_LOW_LEFT,
    .n_steps = 2,
    .steps = {{LOW_BATT_COLOR, 300}, {0, GAP_MS}},
};

static const struct signal low_right_signal = {
    .kind = SIG_LOW_RIGHT,
    .n_steps = 4,
    .steps = {{LOW_BATT_COLOR, FAST_BLINK_MS},
              {0, FAST_BLINK_MS},
              {LOW_BATT_COLOR, FAST_BLINK_MS},
              {0, GAP_MS}},
};

static struct k_spinlock lock;
static struct signal queue[QUEUE_LEN]; /* queue[q_head] is the one playing (if playing) */
static uint8_t q_head, q_count;
static bool playing;
static uint8_t cur_step;
static int64_t step_end;

/* ---------- keyboard state ---------- */

static bool ready;
static bool caps_on;
static bool idle;
static bool asleep;
static uint8_t left_battery, right_battery; /* percent; 0 = not known yet */

static uint32_t shown = UINT32_MAX; /* color currently on the LED (UINT32_MAX = unknown) */
static bool powered;

static void led_work_handler(struct k_work *work);
static K_WORK_DELAYABLE_DEFINE(led_work, led_work_handler);

static void refresh(void) { k_work_reschedule(&led_work, K_NO_WAIT); }

/* ---------- talking to the LED ---------- */

static uint8_t scale(uint32_t channel) {
    return (uint8_t)(((channel & 0xFF) * BRIGHTNESS + 50) / 100);
}

static void set_light(uint32_t color) {
    if (color == shown) {
        return;
    }
    shown = color;

#if HAS_POWER_PIN
    if (color == 0) {
        gpio_pin_set_dt(&power_pin, 0);
        powered = false;
        return;
    }
    if (!powered) {
        gpio_pin_set_dt(&power_pin, 1);
        powered = true;
        k_msleep(1); /* let the LED's own chip start up */
    }
#endif

    struct led_rgb pixel = {.r = scale(color >> 16), .g = scale(color >> 8), .b = scale(color)};
    int err = led_strip_update_rgb(strip, &pixel, 1);
    if (err) {
        LOG_WRN("LED update failed (%d)", err);
    }
}

/* ---------- deciding what to show ---------- */

static bool is_below_caps(int layer) {
    for (int i = 0; i < NUM_BELOW_CAPS; i++) {
        if (below_caps_layers[i] == layer) {
            return true;
        }
    }
    return false;
}

/* highest active layer with a color, looking only at above- or below-Caps-Lock layers */
static uint32_t layer_color(bool below_caps) {
    for (int layer = NUM_LAYER_COLORS - 1; layer >= 0; layer--) {
        if (layer_colors[layer] != 0 && is_below_caps(layer) == below_caps &&
            zmk_keymap_layer_active(layer)) {
            return layer_colors[layer];
        }
    }
    return 0;
}

static uint32_t steady_color(bool caps) {
    uint32_t color = layer_color(false);
    if (color == 0 && caps) {
        color = CAPS_COLOR;
    }
    if (color == 0) {
        color = layer_color(true);
    }
    return color;
}

static void led_work_handler(struct k_work *work) {
    if (!ready || asleep) {
        return;
    }

    uint32_t color = 0;
    int64_t now = k_uptime_get();
    int64_t wake_in = -1;

    k_spinlock_key_t key = k_spin_lock(&lock);
    while (q_count > 0) {
        const struct signal *sig = &queue[q_head];
        if (!playing) {
            playing = true;
            cur_step = 0;
            step_end = now + sig->steps[0].ms;
        } else if (now >= step_end) {
            cur_step++;
            if (cur_step >= sig->n_steps) { /* finished: move on to the next signal */
                playing = false;
                q_head = (q_head + 1) % QUEUE_LEN;
                q_count--;
                continue;
            }
            step_end = now + sig->steps[cur_step].ms;
        }
        color = sig->steps[cur_step].color;
        wake_in = step_end - now;
        break;
    }
    bool show_steady = (q_count == 0) && !(IDLE_OFF && idle);
    bool caps = caps_on;
    k_spin_unlock(&lock, key);

    if (show_steady) {
        color = steady_color(caps);
    }
    set_light(color);

    if (wake_in >= 0) {
        k_work_reschedule(&led_work, K_MSEC(wake_in));
    }
}

/* Add a signal to the queue. A waiting signal of the same kind is replaced instead,
 * so e.g. switching profiles twice quickly blinks only the final profile. */
static void enqueue(const struct signal *sig) {
    k_spinlock_key_t key = k_spin_lock(&lock);
    bool placed = false;
    for (int i = playing ? 1 : 0; i < q_count; i++) {
        struct signal *waiting = &queue[(q_head + i) % QUEUE_LEN];
        if (waiting->kind == sig->kind) {
            *waiting = *sig;
            placed = true;
            break;
        }
    }
    if (!placed && q_count < QUEUE_LEN) {
        queue[(q_head + q_count) % QUEUE_LEN] = *sig;
        q_count++;
    }
    k_spin_unlock(&lock, key);
    refresh();
}

#if IS_ENABLED(CONFIG_ZMK_BLE)
static void signal_bt_profile(uint8_t index) {
    struct signal sig = {.kind = SIG_BT_PROFILE};
    int blinks = MIN(index + 1, MAX_STEPS / 2);
    for (int i = 0; i < blinks; i++) {
        sig.steps[sig.n_steps++] = (struct step){BT_COLOR, BLINK_MS};
        sig.steps[sig.n_steps++] = (struct step){0, BLINK_MS};
    }
    sig.steps[sig.n_steps - 1].ms = GAP_MS;
    enqueue(&sig);
}
#endif

static bool is_low(uint8_t percent) { return percent > 0 && percent < LOW_BATT_PERCENT; }

/* power-on / wake battery check (waking from deep sleep restarts the keyboard) */
static void battery_check_handler(struct k_work *work) {
#if IS_ENABLED(CONFIG_ZMK_BATTERY_REPORTING)
    uint8_t percent = zmk_battery_state_of_charge();
    if (percent == 0) {
        return; /* no reading yet */
    }
    left_battery = percent;
    uint32_t color = percent > 50 ? BATT_GOOD_COLOR
                     : percent >= LOW_BATT_PERCENT ? BATT_MEDIUM_COLOR
                                                   : LOW_BATT_COLOR;
    struct signal sig = {
        .kind = SIG_BATTERY_CHECK,
        .n_steps = 2,
        .steps = {{color, 1000}, {0, GAP_MS}},
    };
    enqueue(&sig);
#endif
}
static K_WORK_DELAYABLE_DEFINE(battery_check_work, battery_check_handler);

static void reminder_handler(struct k_work *work) {
    if (zmk_activity_get_state() == ZMK_ACTIVITY_ACTIVE) {
        if (is_low(left_battery)) {
            enqueue(&low_left_signal);
        }
        if (is_low(right_battery)) {
            enqueue(&low_right_signal);
        }
    }
    k_work_schedule(k_work_delayable_from_work(work), K_MSEC(REMINDER_PERIOD_MS));
}
static K_WORK_DELAYABLE_DEFINE(reminder_work, reminder_handler);

/* ---------- reacting to keyboard events ---------- */

static int status_led_listener(const zmk_event_t *eh) {
    const struct zmk_activity_state_changed *activity = as_zmk_activity_state_changed(eh);
    if (activity) {
        if (activity->state == ZMK_ACTIVITY_SLEEP) {
            /* Runs right before deep sleep: switch the LED off now, while we still can. */
            asleep = true;
            k_work_cancel_delayable(&led_work);
            set_light(0);
        } else {
            asleep = false;
            idle = (activity->state == ZMK_ACTIVITY_IDLE);
            refresh();
        }
        return ZMK_EV_EVENT_BUBBLE;
    }

    const struct zmk_hid_indicators_changed *indicators = as_zmk_hid_indicators_changed(eh);
    if (indicators) {
        caps_on = (indicators->indicators & HID_CAPS_LOCK_BIT) != 0;
        refresh();
        return ZMK_EV_EVENT_BUBBLE;
    }

    if (as_zmk_layer_state_changed(eh)) {
        refresh();
        return ZMK_EV_EVENT_BUBBLE;
    }

#if IS_ENABLED(CONFIG_ZMK_BLE)
    const struct zmk_ble_active_profile_changed *profile = as_zmk_ble_active_profile_changed(eh);
    if (profile) {
        if (k_uptime_get() > BOOT_QUIET_MS) {
            signal_bt_profile(profile->index);
        }
        return ZMK_EV_EVENT_BUBBLE;
    }
#endif

#if IS_ENABLED(CONFIG_ZMK_BATTERY_REPORTING)
    const struct zmk_battery_state_changed *battery = as_zmk_battery_state_changed(eh);
    if (battery) {
        left_battery = battery->state_of_charge;
        return ZMK_EV_EVENT_BUBBLE;
    }
#endif

#if IS_ENABLED(CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING)
    const struct zmk_peripheral_battery_state_changed *peripheral =
        as_zmk_peripheral_battery_state_changed(eh);
    if (peripheral) {
        if (peripheral->source == 0) { /* the only peripheral: the right half */
            right_battery = peripheral->state_of_charge;
        }
        return ZMK_EV_EVENT_BUBBLE;
    }
#endif

    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(cirrus_status_led, status_led_listener);
ZMK_SUBSCRIPTION(cirrus_status_led, zmk_activity_state_changed);
ZMK_SUBSCRIPTION(cirrus_status_led, zmk_hid_indicators_changed);
ZMK_SUBSCRIPTION(cirrus_status_led, zmk_layer_state_changed);
#if IS_ENABLED(CONFIG_ZMK_BLE)
ZMK_SUBSCRIPTION(cirrus_status_led, zmk_ble_active_profile_changed);
#endif
#if IS_ENABLED(CONFIG_ZMK_BATTERY_REPORTING)
ZMK_SUBSCRIPTION(cirrus_status_led, zmk_battery_state_changed);
#endif
#if IS_ENABLED(CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING)
ZMK_SUBSCRIPTION(cirrus_status_led, zmk_peripheral_battery_state_changed);
#endif

/* ---------- start-up ---------- */

static int status_led_init(void) {
    if (!device_is_ready(strip)) {
        LOG_ERR("Status LED driver not ready");
        return -ENODEV;
    }
#if HAS_POWER_PIN
    if (!device_is_ready(power_pin.port)) {
        LOG_ERR("Status LED power pin not ready");
        return -ENODEV;
    }
    gpio_pin_configure_dt(&power_pin, GPIO_OUTPUT_INACTIVE);
#endif
    shown = 0; /* LED starts unpowered (dark) */
    ready = true;

    k_work_schedule(&battery_check_work, K_MSEC(1500));
    k_work_schedule(&reminder_work, K_MSEC(REMINDER_PERIOD_MS));
    refresh();
    return 0;
}

SYS_INIT(status_led_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);
