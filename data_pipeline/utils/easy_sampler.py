import random
from easy_dict import EASY_DICT

def weighted_choice(items: dict, k=1):
    """
    Selects k keys from a dict {item: weight}
    """
    keys = list(items.keys())
    weights = list(items.values())
    return random.choices(keys, weights=weights, k=k)

def sample_keywords(
    easy_dict,
    num_category_probs={1: 0.4, 2: 0.4, 3: 0.2}
):
    """
    Samples categories and one sub-item per category.

    Returns:
        dict: {category_name: selected_item}
    """

    # --- Step 1: sample number of categories ---
    num_categories = weighted_choice(num_category_probs)[0]
    num_categories = min(num_categories, len(easy_dict))

    # --- Step 2: sample categories (weighted, without replacement) ---
    categories = list(easy_dict.keys())
    category_weights = [easy_dict[c]["prob"] for c in categories]

    selected_categories = random.choices(
        categories,
        weights=category_weights,
        k=num_categories
    )

    # remove duplicates while preserving order
    selected_categories = list(dict.fromkeys(selected_categories))

    while len(selected_categories) < num_categories:
        extra = random.choices(categories, weights=category_weights, k=1)[0]
        if extra not in selected_categories:
            selected_categories.append(extra)

    # --- Step 3: sample sub-items ---
    selected = {}
    for category in selected_categories:
        selected[category] = weighted_choice(
            easy_dict[category]["items"]
        )[0]

    return selected


# ---- Example usage ----
if __name__ == "__main__":
    for _ in range(1):
        print(sample_keywords(EASY_DICT))
