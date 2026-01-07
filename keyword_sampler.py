import random
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

def sample_prompt():
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

    # Compose prompt (example, can be customized)
    prompt = f"{edit_verb.capitalize()} {edit_target.format(garment_type=garment_type)} {edit_result.format(description=f'{garment_color} {garment_material} {garment_pattern} {garment_surface}')} " \
             f"with {fit_overall} fit, {fit_length} length, {fit_neckline} neckline, {fit_waist} waist, {fit_cut} cut. " \
             f"Scene: {scene_bg}, {scene_light}, {scene_quality}. " \
             f"Style: {style_aesthetic}, {style_occasion}, {style_season}. " \
             f"Observed: {obs_garment}, {obs_body}, {obs_skin}, {obs_pose}, {obs_camera}, {obs_visible}. " \
             f"Complexity: {complexity_example}"
    return prompt

if __name__ == "__main__":
    # Example: sample 5 prompts
    for _ in range(5):
        print(sample_prompt())
