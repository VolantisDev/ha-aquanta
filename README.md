# Aquanta Water Heater Controller for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

Component to integrate with [Aquanta Smart Water Heater Controllers][aquanta] through their undocumented cloud API.

**This component will set up the following platforms.**

| Platform        | Description                                |
| --------------- | ------------------------------------------ |
| `water_heater`  | Set temperature, operation mode, and Away mode.        |
| `sensor`        | Additional data about each Aquanta device  |
| `binary_sensor` | On/Off values for various Aquanta settings |
| `switch`        | Supports toggling Away and Boost modes     |

This integration uses cloud polling to update the data about your water heater controllers regularly.

Note: This is an unofficial integration that is not related to the Aquanta company in any way. There is no official public API yet, so the API being used is undocumented and could change (or be removed) at any point.

## Installation

### Option 1: HACS (Recommended)

1. Add this repository to HACS.
2. Search for "Aquanta" under "Integrations".
3. Install the integration.
4. Restart Home Assistant.

### Option 2: Manual

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `aquanta`.
4. Download _all_ the files from the `custom_components/aquanta/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant.


## Configuration

All configuration is done in the UI.

1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Aquanta".
2. Enter your Aquanta account email address and password in the form and submit to add the integration.

Your Aquanta devices should now show up in Home Assistant and the device data will be updated from the cloud every 60s by default.

### Options

Use "Configure" on the integration to set the **Away duration** (in days) used when Away mode is turned on. Set it to `0` to keep Away on until it is turned off again.

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

***

[aquanta]: https://aquanta.io/
[buymecoffee]: https://www.buymeacoffee.com/benmcclure
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/bmcclure/ha-aquanta.svg?style=for-the-badge
[commits]: https://github.com/bmcclure/ha-aquanta/commits/master
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/custom-components/blueprint.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Ben%20McClure%20%40bmcclure-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/bmcclure/ha-aquanta.svg?style=for-the-badge
[releases]: https://github.com/bmcclure/ha-aquanta/releases
