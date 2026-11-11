# Custom behaviors for the Cirrus. Keymap behaviors run on the central (left) half only.
if ((NOT CONFIG_ZMK_SPLIT) OR CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
  target_sources_ifdef(CONFIG_ZMK_BEHAVIOR_BT_PROFILE_TOGGLE app PRIVATE src/behaviors/behavior_bt_profile_toggle.c)
endif()

# Status light (left half)
target_sources_ifdef(CONFIG_ZMK_CIRRUS_STATUS_LED app PRIVATE src/cirrus_status_led.c)
