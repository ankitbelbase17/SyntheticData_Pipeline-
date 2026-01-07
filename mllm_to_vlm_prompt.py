import json

def fill_json_placeholders(json_data):
    """
    Fill missing or placeholder values in the JSON with reasonable defaults.
    For example, if a value is None or a placeholder string, fill with a default.
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
            "visible_elements": "full body visible"
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
    for section, values in defaults.items():
        if section not in json_data:
            json_data[section] = values
        else:
            for k, v in values.items():
                if k not in json_data[section] or json_data[section][k] is None:
                    json_data[section][k] = v
    return json_data

def mllm_generate_vlm_prompt(json_data):
    """
    Use the filled JSON to generate a structured prompt for the VLM.
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
        "task": "Generate editing prompt for edit-based model",
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
            "Result: {}".format(editing["result_specification"].replace("{description}", f'{garment["color"]} {garment["material"]} {garment["pattern"]} {garment["surface_detail"]}'))
        ],
        "output_format": "Natural language prompt for edit-based editing model"
    }
    return prompt

if __name__ == "__main__":
    # Example usage: load JSON from sampler, fill placeholders, generate VLM prompt
    from keyword_sampler import sample_prompt_json
    for _ in range(3):
        sampled_json = sample_prompt_json()
        filled_json = fill_json_placeholders(sampled_json)
        vlm_prompt = mllm_generate_vlm_prompt(filled_json)
        print(json.dumps(vlm_prompt, indent=2))
