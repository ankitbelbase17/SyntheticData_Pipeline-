"""
Simple keyword sampler from people_western_dict.py
"""
import json
import random
import re
import ast
from pathlib import Path


def load_people_dict(path=None):
    """Load people_western_dict.py as a Python dict."""
    if path is None:
        # Get the directory where this script is located
        script_dir = Path(__file__).parent
        path = script_dir / "people_western_dict.py"
    else:
        path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    
    raw = path.read_text(encoding="utf-8")
    
    # Try JSON first
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    
    # Try literal_eval for Python dict format
    try:
        data = ast.literal_eval(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    
    raise ValueError("Could not parse people_western_dict.py as dict")


def sanitize_name(s: str) -> str:
    """Clean a string for use in filenames."""
    s = s.strip().lower()
    s = re.sub(r"[\/\\\s]+", "_", s)  # replace slashes/spaces with underscore
    s = re.sub(r"[^a-z0-9_.-]", "", s)  # keep only alphanumeric, underscore, dot, dash
    return s[:200]  # limit length


def weighted_choice(items, weights):
    """Select an item based on weights."""
    return random.choices(items, weights=weights, k=1)[0]


def select_from_category(category_data, category_name=""):
    """Select one keyword from a category using probabilities."""
    
    if isinstance(category_data, dict):
        # Body type
        if "body_types" in category_data:
            body_types = category_data["body_types"]
            types = list(body_types.keys())
            probs = [body_types[t].get("prob", 1.0/len(types)) for t in types]
            return weighted_choice(types, probs)
        
        # Countries/Ethnicities - return tuple (country, ethnicity)
        elif category_name == "countries_ethnicities":
            countries = list(category_data.keys())
            country_probs = []
            for c in countries:
                country_entry = category_data[c]
                if isinstance(country_entry, dict):
                    country_probs.append(country_entry.get("prob", 1.0/len(countries)))
                else:
                    country_probs.append(1.0/len(countries))
            
            country = weighted_choice(countries, country_probs)
            country_entry = category_data[country]
            
            if isinstance(country_entry, dict):
                ethnicities = country_entry.get("ethnicities", [])
            else:
                ethnicities = country_entry if isinstance(country_entry, list) else []
            
            ethnicity = random.choice(ethnicities) if ethnicities else "unknown"
            return (country, ethnicity)
        
        # Gender (returns gender, clothing tuple)
        elif category_name == "gender":
            genders = list(category_data.keys())
            gender_probs = [category_data[g].get("prob", 0.5) for g in genders]
            gender = weighted_choice(genders, gender_probs)
            clothing = random.choice(category_data[gender].get("clothing", ["casual wear"]))
            return (gender, clothing)
        
        # Photo style (returns style, attributes tuple)
        elif category_name == "photo_style":
            styles = list(category_data.keys())
            style_probs = [category_data[s].get("prob", 1.0/len(styles)) for s in styles]
            style = weighted_choice(styles, style_probs)
            attributes = category_data[style].get("attributes", {})
            return (style, attributes)
        
        # Disabilities
        elif category_name == "disabilities_visible":
            none_prob = category_data.get("none", {}).get("prob", 0.8)
            if random.random() < none_prob:
                return "none"
            disability_data = category_data.get("with_disability", {})
            types = disability_data.get("types", ["none"])
            return random.choice(types)
        
        # Generic weighted dict
        else:
            items = list(category_data.keys())
            probs = [category_data[i].get("prob", 1.0/len(items)) for i in items]
            return weighted_choice(items, probs)
    
    elif isinstance(category_data, list):
        return random.choice(category_data)
    
    return str(category_data) if category_data else ""


def sample_keywords(people_dict):
    """Sample one set of keywords from people_dict."""
    keywords = {}
    
    for category, category_data in people_dict.items():
        result = select_from_category(category_data, category)
        
        # Special handling for countries_ethnicities tuple
        if category == "countries_ethnicities" and isinstance(result, tuple):
            keywords["country"] = result[0]
            keywords["country_ethnicity"] = result[1]
        # Special handling for gender tuple
        elif category == "gender" and isinstance(result, tuple):
            keywords["gender"] = result[0]
            keywords["clothing"] = result[1]
        # Special handling for photo_style tuple
        elif category == "photo_style" and isinstance(result, tuple):
            keywords["photo_style"] = result[0]
            for attr_key, attr_val in result[1].items():
                keywords[f"photo_{attr_key}"] = attr_val
        else:
            keywords[category] = result
    
    return keywords


if __name__ == "__main__":
    # Load people dictionary
    people_dict = load_people_dict()
    
    # Sample 5 keyword sets
    # print("Sampling 5 keyword sets:\n")
    for i in range(1):
        kw = sample_keywords(people_dict)
        
        # Create sanitized filename
        country = sanitize_name(kw.get("country", ""))
        ethnicity = sanitize_name(kw.get("country_ethnicity", ""))
        gender = sanitize_name(kw.get("gender", ""))
        specs = sanitize_name(kw.get("spectacles", ""))
        disability = sanitize_name(kw.get("disabilities_visible", ""))
        
        # filename = f"{country}_{ethnicity}_{gender}_{specs}_{disability}"
        
        # print(f"{i+1}. Filename: {filename}")
        print(f" {kw}")
        print()