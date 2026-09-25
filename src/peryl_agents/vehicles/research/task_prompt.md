# Missing Vehicle Specifications

Research the supplied vehicles using live web search and fill only the fields
listed in each vehicle's `missing_fields`. The supplied `existing_specs` are
context; preserve them and return `null` for fields that are already populated.

Prefer manufacturer specification sheets, brochures, manuals, and original
equipment information. Use reputable secondary sources when primary sources
are unavailable. Open the source and verify that it supports the returned value
for the exact make, model, trim, and model-year range.

Do not add vehicles or change their identity or year range. If available sources
cannot establish a single applicable value across the supplied range, or the
value depends on an unspecified variant, return `null` for that field. Do not
invent values or source URLs.

## Fields and units

* `width_mm`: overall body width excluding mirrors, in millimetres.
* `length_mm`: overall vehicle length, in millimetres.
* `height_mm`: overall height with standard equipment, in millimetres.
* `curb_weight_kg`: curb weight, not gross vehicle weight, payload, or dry weight,
  in kilograms.
* `stock_tire_class`: the integer ID from the supplied tire-class mapping for
  the vehicle's original equipment tires. Research the original tires before
  assigning a class; do not infer it merely from the vehicle's body style. If
  original equipment choices do not establish one class, return `null`.

Convert measurements to the requested units and round to the nearest whole
millimetre or kilogram. All returned values must be positive integers.

## Sources and confidence

Each researched field must contain its value, the URL supporting it, and an
integer confidence score from 1 to 5:

* 5: direct manufacturer or original equipment evidence for the exact vehicle.
* 4: clear, consistent evidence from a reputable specification source.
* 3: applicable evidence with limited corroboration.
* 2: weak evidence for the applicable specification.
* 1: very weak evidence that still supports a specific value.

Low confidence is not a substitute for an unknown or conflicting value; return
`null` when the value cannot be established. The task records the write timestamp.

## Output

Return only JSON matching the supplied schema, with a top-level `data` list.
Return one result per supplied vehicle, using its exact `vehicle_id`. Include
all five specification keys in each result, using `null` for unknown or
unrequested fields. A populated field has exactly `value`, `source_url`, and
`confidence`; do not add explanations or timestamps to the JSON.
