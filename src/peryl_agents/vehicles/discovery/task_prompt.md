# Missing Vehicle Examples

Review the provided existing vehicle examples and identify important missing vehicles that should be added.

Use live web search where necessary to verify the vehicle model, trim, and applicable model-year range.

Aim for broad, representative coverage of commonly used production vehicles.

Consider gaps across:

* manufacturers
* vehicle classes
* body styles
* sizes
* powertrains
* major market segments

Prefer widely produced or commonly encountered vehicles over obscure, rare, limited-production, or concept vehicles.

## Model-year range

For each vehicle, determine the continuous range of model years for which the specified **make + model + trim corresponds to substantially the same vehicle specification**.

`model_year_start` and `model_year_end` are NOT simply the model year of the source you found.

Search backwards and forwards from a known model year to determine when that configuration began and when it ended.

The range should end when there is a major change that could materially affect vehicle specifications, including:

* a new vehicle generation or major redesign
* a substantial body or chassis redesign
* a change in wheelbase or major exterior dimensions
* a trim being introduced, discontinued, or materially redefined
* a major powertrain/platform change where it changes the representative vehicle configuration

Minor annual changes such as colours, infotainment updates, small styling changes, option-package changes, or minor equipment changes should generally NOT create a new range.

For example, if a trim has effectively the same dimensions and underlying vehicle configuration from model years 2022 through 2024, return:

`model_year_start: 2022`
`model_year_end: 2024`

Do NOT return `2024` to `2024` merely because the source used to identify the vehicle describes the 2024 model year.

A one-year range is appropriate only when the configuration genuinely existed for one model year, or when reliable evidence indicates a material change immediately before and after that year.

## Output

For each missing vehicle return:

* the canonical manufacturer name
* the canonical model name
* the canonical trim name
* `model_year_start`: the first model year of the materially equivalent configuration
* `model_year_end`: the final model year of the materially equivalent configuration

Before returning each vehicle, explicitly verify that the start and end years represent the configuration's applicable production period rather than merely the year mentioned by a source.
