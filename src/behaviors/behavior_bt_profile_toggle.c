/*
 * Bluetooth profile toggle: one key flips between two profiles.
 * If profile A is active, switch to profile B; otherwise switch to profile A.
 * It asks the keyboard which profile is active, so it never gets out of sync.
 */

#define DT_DRV_COMPAT zmk_behavior_bt_profile_toggle

#include <zephyr/device.h>
#include <zephyr/logging/log.h>

#include <drivers/behavior.h>

#include <zmk/behavior.h>
#include <zmk/ble.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)

struct behavior_bt_profile_toggle_config {
    uint8_t profile_a;
    uint8_t profile_b;
};

static int on_keymap_binding_pressed(struct zmk_behavior_binding *binding,
                                     struct zmk_behavior_binding_event event) {
    const struct device *dev = zmk_behavior_get_binding(binding->behavior_dev);
    const struct behavior_bt_profile_toggle_config *cfg = dev->config;

    int current = zmk_ble_active_profile_index();
    uint8_t target = (current == cfg->profile_a) ? cfg->profile_b : cfg->profile_a;

    LOG_DBG("BT profile toggle: %d -> %d", current, target);
    zmk_ble_prof_select(target);
    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_keymap_binding_released(struct zmk_behavior_binding *binding,
                                      struct zmk_behavior_binding_event event) {
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api behavior_bt_profile_toggle_driver_api = {
    .binding_pressed = on_keymap_binding_pressed,
    .binding_released = on_keymap_binding_released,
#if IS_ENABLED(CONFIG_ZMK_BEHAVIOR_METADATA)
    .get_parameter_metadata = zmk_behavior_get_empty_param_metadata,
#endif
};

#define BT_TOGGLE_INST(n)                                                                          \
    static const struct behavior_bt_profile_toggle_config behavior_bt_profile_toggle_config_##n = { \
        .profile_a = DT_INST_PROP(n, profile_a),                                                   \
        .profile_b = DT_INST_PROP(n, profile_b),                                                   \
    };                                                                                             \
    BEHAVIOR_DT_INST_DEFINE(n, NULL, NULL, NULL, &behavior_bt_profile_toggle_config_##n,           \
                            POST_KERNEL, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT,                      \
                            &behavior_bt_profile_toggle_driver_api);

DT_INST_FOREACH_STATUS_OKAY(BT_TOGGLE_INST)

#endif /* DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT) */
