import random
import json
from keywords_dictionary import VTON_DICTIONARY

def weighted_choice(items):
    """items: list of (item, prob) tuples. Returns one item according to prob."""
    total = sum(prob for _, prob in items)
    r = random.uniform(0, total)
    upto = 0
    for item, prob in items:
        if upto + prob >= r:
            return item
        upto += prob
    return items[-1][0]  # fallback

def sample_hierarchical_keywords(dictionary, depth=2):
    """Recursively sample keywords from the hierarchical dictionary up to a certain depth."""
    result = {}
    for key, value in dictionary.items():
        if key == 'prob':
            continue
        if isinstance(value, dict) and 'keywords' in value:
            # This is a leaf node with keywords
            kw = weighted_choice(value['keywords'])
            result[key] = kw
        elif isinstance(value, dict):
            # This is a sub-dictionary
            if 'prob' in value and random.random() < value['prob']:
                result[key] = sample_hierarchical_keywords(value, depth-1) if depth > 0 else None
        # else: skip non-dict
    return result


def sample_component_keywords(component_dict):
    """Sample a keyword from a component dict with hierarchical probabilities."""
    if not isinstance(component_dict, dict):
        return None
    # If this is a leaf with keywords
    if 'keywords' in component_dict:
        return weighted_choice(component_dict['keywords'])
    # Otherwise, sample a subcomponent
    choices = [(k, v['prob']) for k, v in component_dict.items() if isinstance(v, dict) and 'prob' in v]
    if not choices:
        return None
    main_key = weighted_choice(choices)
    return sample_component_keywords(component_dict[main_key])

def sample_prompt_json():
    garment = VTON_DICTIONARY['garment']
    fit = VTON_DICTIONARY['fit']
    observed = VTON_DICTIONARY['observed_elements']
    scene = VTON_DICTIONARY['scene']
    editing = VTON_DICTIONARY['editing_actions']
    style = VTON_DICTIONARY['style_context']
    complexity = VTON_DICTIONARY['complexity']

    # Garment
    garment_type = sample_component_keywords(garment['type'])
    garment_color = sample_component_keywords(garment['color'])
    garment_material = sample_component_keywords(garment['material'])
    garment_pattern = sample_component_keywords(garment['pattern'])
    garment_surface = sample_component_keywords(garment['surface_detail'])

    # Fit
    fit_overall = sample_component_keywords(fit['overall_fit'])
    fit_length = sample_component_keywords(fit['length'])
    fit_neckline = sample_component_keywords(fit['neckline'])
    fit_waist = sample_component_keywords(fit['waist'])
    fit_cut = sample_component_keywords(fit['cut_style'])

    # Observed elements
    obs_garment = sample_component_keywords(observed['current_garment'])
    obs_body = sample_component_keywords(observed['body_characteristics'])
    obs_skin = sample_component_keywords(observed['skin_tone'])
    obs_pose = sample_component_keywords(observed['pose_type'])
    obs_camera = sample_component_keywords(observed['camera_view'])
    obs_visible = sample_component_keywords(observed['visible_elements'])
    obs_age = sample_component_keywords(observed['age_group'])
    obs_gender = sample_component_keywords(observed['gender'])
    obs_body_shape = sample_component_keywords(observed['body_shape'])

    # Scene
    scene_bg = sample_component_keywords(scene['background'])
    scene_light = sample_component_keywords(scene['lighting'])
    scene_quality = sample_component_keywords(scene['image_quality'])

    # Editing
    edit_verb = sample_component_keywords(editing['primary_verbs'])
    edit_preserve = sample_component_keywords(editing['preservation_verbs'])
    edit_target = sample_component_keywords(editing['target_specification'])
    edit_result = sample_component_keywords(editing['result_specification'])

    # Style
    style_aesthetic = sample_component_keywords(style['aesthetic'])
    style_occasion = sample_component_keywords(style['occasion'])
    style_season = sample_component_keywords(style['season'])

    # Complexity
    complexity_choices = [(k, v['prob']) for k, v in complexity.items() if k != 'prob']
    complexity_key = weighted_choice(complexity_choices)
    complexity_example = complexity[complexity_key]['example']

    # Output as JSON
    output = {
        "garment": {
            "type": garment_type,
            "color": garment_color,
            "material": garment_material,
            "pattern": garment_pattern,
            "surface_detail": garment_surface
        },
        "fit": {
            "overall_fit": fit_overall,
            "length": fit_length,
            "neckline": fit_neckline,
            "waist": fit_waist,
            "cut_style": fit_cut
        },
        "observed_elements": {
            "current_garment": obs_garment,
            "body_characteristics": obs_body,
            "skin_tone": obs_skin,
            "pose_type": obs_pose,
            "camera_view": obs_camera,
            "visible_elements": obs_visible,
            "age_group": obs_age,
            "gender": obs_gender,
            "body_shape": obs_body_shape
        },
        "scene": {
            "background": scene_bg,
            "lighting": scene_light,
            "image_quality": scene_quality
        },
        "editing_actions": {
            "primary_verb": edit_verb,
            "preservation_verb": edit_preserve,
            "target_specification": edit_target,
            "result_specification": edit_result
        },
        "style_context": {
            "aesthetic": style_aesthetic,
            "occasion": style_occasion,
            "season": style_season
        },
        "complexity": {
            "level": complexity_key,
            "example": complexity_example
        }
    }

    return output

def sample_keywords_hierarchical():
    """Sample keywords from the hierarchical dictionary and return as a dictionary."""
    return sample_prompt_json()

if __name__ == "__main__":
    result = sample_prompt_json()
    print(json.dumps(result, indent=2))
