
import random
from easy_dict import EASY_DICT


def weighted_choice(items: dict, k=1):
    """
    Selects k keys from a dict {item: weight}
    """
    keys = list(items.keys())
    weights = list(items.values())
    return random.choices(keys, weights=weights, k=k)


def sample_keywords(easy_dict):
    """
    Samples categories independently using their category probabilities.
    From each selected category, samples exactly one sub-item.

    Returns:
        dict: {category_name: selected_item}
    """

    selected = {}

    # --- Step 1: sample categories independently ---
    for category, data in easy_dict.items():
        if random.random() < data["prob"]:
            selected[category] = weighted_choice(
                data["items"]
            )[0]

    # --- Step 2: ensure at least one category is selected ---
    if not selected:
        categories = list(easy_dict.keys())
        category_weights = [easy_dict[c]["prob"] for c in categories]
        category = random.choices(categories, weights=category_weights, k=1)[0]
        selected[category] = weighted_choice(
            easy_dict[category]["items"]
        )[0]

    return selected


# ---- Example usage ----
if __name__ == "__main__":
    for _ in range(1):
        print(sample_keywords(EASY_DICT))
