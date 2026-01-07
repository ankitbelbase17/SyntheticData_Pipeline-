import json


def fill_json_placeholders_and_correct(json_data):
    """
    Fill missing/placeholder values and correct implausible or invalid combinations in the JSON.
    Only correct placeholders or implausible values, not valid creative combinations.
    """
    defaults = {
        "garment": {
            "type": "t-shirt",
            "color": "black",
            "material": "cotton",
            "pattern": "solid color",
            "surface_detail": "plain"
        },
        "fit": {
            "overall_fit": "regular fit",
            "length": "regular length",
            "neckline": "crew neck",
            "waist": "mid-rise",
            "cut_style": "straight cut"
        },
        "observed_elements": {
            "current_garment": "describe current garment type",
            "body_characteristics": "average build",
            "skin_tone": "medium skin",
            "pose_type": "standing straight",
            "camera_view": "front view",
            "visible_elements": "full body visible",
            "age_group": "adult",
            "gender": "female",
            "body_shape": "mesomorph"
        },
        "scene": {
            "background": "plain white background",
            "lighting": "soft natural lighting",
            "image_quality": "high resolution"
        },
        "editing_actions": {
            "primary_verb": "change",
            "preservation_verb": "keep",
            "target_specification": "the {garment_type}",
            "result_specification": "into a {description}"
        },
        "style_context": {
            "aesthetic": "casual",
            "occasion": "everyday wear",
            "season": "all-season"
        },
        "complexity": {
            "level": "simple",
            "example": "Change the {current} to a {color} {garment_type}"
        }
    }
    # Fill missing/placeholder values
    for section, values in defaults.items():
        if section not in json_data:
            json_data[section] = values
        else:
            for k, v in values.items():
                if k not in json_data[section] or json_data[section][k] is None:
                    json_data[section][k] = v

    # Correction logic for implausible combinations
    garment_type = json_data["garment"]["type"].lower()
    gender = json_data["observed_elements"].get("gender", "female").lower()
    # Example: sari on a man, blouse with half-pants, etc.
    implausible = False
    # Sari/lehenga/dupatta/kimono/hanbok/abaya/kaftan on male
    if gender == "male" and any(x in garment_type for x in ["sari", "lehenga", "dupatta", "kimono", "hanbok", "abaya", "kaftan", "choli", "dirndl", "qipao", "cheongsam"]):
        json_data["garment"]["type"] = "kurta"
        implausible = True
    # Blouse with shorts/half-pants
    if garment_type == "blouse" and json_data["fit"].get("length", "").lower() in ["shorts", "half-pants"]:
        json_data["fit"]["length"] = "regular length"
        implausible = True
    # Sari with non-female body shape
    if "sari" in garment_type and gender != "female":
        json_data["garment"]["type"] = "kurta"
        implausible = True
    # Add more rules as needed for your domain
    # (e.g., child with tuxedo, senior with romper, etc.)
    # Only correct if clearly implausible
    return json_data

def mllm_generate_vlm_prompt(json_data):
    """
    Use the filled and corrected JSON to generate a structured, high-signal prompt for the VLM.
    """
    garment = json_data["garment"]
    fit = json_data["fit"]
    observed = json_data["observed_elements"]
    scene = json_data["scene"]
    editing = json_data["editing_actions"]
    style = json_data["style_context"]
    complexity = json_data["complexity"]

    prompt = {
        "role": "Vision-Language Model (VLM)",
        "task": "Generate a realistic, actionable editing prompt for an edit-based model, using only plausible and contextually valid attribute combinations.",
        "context": {
            "garment": garment,
            "fit": fit,
            "observed_elements": observed,
            "scene": scene,
            "style_context": style,
            "complexity": complexity
        },
        "constraints": [
            "Editing action: {}".format(editing["primary_verb"]),
            "Preservation: {}".format(editing["preservation_verb"]),
            "Target: {}".format(editing["target_specification"].replace("{garment_type}", garment["type"])),
            "Result: {}".format(editing["result_specification"].replace("{description}", f'{garment["color"]} {garment["material"]} {garment["pattern"]} {garment["surface_detail"]}')),
            "Ensure all attribute combinations are plausible for the given age group, gender, and body shape. If not, correct them to the nearest plausible value."
        ],
        "output_format": "A single, natural language prompt for the edit-based editing model."
    }
    return prompt

if __name__ == "__main__":
    # Example usage: load JSON from sampler, fill placeholders, correct implausible combos, generate VLM prompt
    from keyword_sampler import sample_prompt_json
    for _ in range(3):
        sampled_json = sample_prompt_json()
        filled_json = fill_json_placeholders_and_correct(sampled_json)
        vlm_prompt = mllm_generate_vlm_prompt(filled_json)
        print(json.dumps(vlm_prompt, indent=2))
