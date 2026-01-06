VTON_DICTIONARY = {
    # 1. GARMENT ATTRIBUTES (Primary editing targets)
    "garment": {
        "type": {
            "tops": [
                "t-shirt", "blouse", "sweater", "tank top", "crop top", 
                "hoodie", "cardigan", "blazer", "button-up shirt", "polo shirt", 
                "turtleneck", "henley", "camisole", "tube top", "halter top"
            ],
            "bottoms": [
                "jeans", "trousers", "shorts", "skirt", "leggings", 
                "joggers", "chinos", "cargo pants", "palazzo pants", 
                "culottes", "capris", "sweatpants", "pleated skirt"
            ],
            "dresses": [
                "maxi dress", "midi dress", "mini dress", "sundress", 
                "cocktail dress", "shirt dress", "wrap dress", "A-line dress",
                "bodycon dress", "slip dress", "sweater dress"
            ],
            "outerwear": [
                "jacket", "coat", "parka", "trench coat", "bomber jacket", 
                "denim jacket", "leather jacket", "windbreaker", "vest",
                "peacoat", "blazer", "kimono", "poncho"
            ],
            "full_body": [
                "jumpsuit", "romper", "overall", "bodysuit", "tracksuit", "onesie"
            ]
        },
        
        "material": {
            # Qwen2-VL understands these fabric properties
            "cotton": ["soft cotton", "thick cotton", "cotton jersey", "organic cotton"],
            "denim": ["light denim", "dark denim", "stretch denim", "rigid denim"],
            "knit": ["chunky knit", "fine knit", "ribbed knit", "cable knit"],
            "silk": ["smooth silk", "silk satin", "raw silk", "silk charmeuse"],
            "wool": ["merino wool", "wool blend", "cashmere", "fleece"],
            "synthetic": ["polyester", "nylon", "spandex blend", "jersey knit"],
            "leather": ["genuine leather", "faux leather", "suede", "patent leather"],
            "linen": ["crisp linen", "wrinkled linen", "linen blend"],
            "texture_keywords": [
                "smooth", "textured", "soft", "stiff", "stretchy", 
                "structured", "flowy", "crisp", "plush", "sleek"
            ]
        },
        
        "color": {
            # Specific enough for Qwen2-VL to understand
            "neutrals": [
                "white", "off-white", "cream", "beige", "tan", "camel",
                "black", "charcoal", "gray", "light gray", "dark gray",
                "navy", "navy blue", "brown", "chocolate brown", "taupe"
            ],
            "warm": [
                "red", "crimson", "burgundy", "maroon", "wine red",
                "orange", "burnt orange", "coral", "rust", "terracotta",
                "yellow", "mustard yellow", "golden yellow", "ochre"
            ],
            "cool": [
                "blue", "royal blue", "cobalt", "sky blue", "powder blue",
                "green", "forest green", "emerald", "olive", "sage green",
                "purple", "lavender", "plum", "violet", "indigo",
                "teal", "turquoise", "aqua", "mint"
            ],
            "pastels": [
                "pastel pink", "blush pink", "baby blue", "mint green",
                "lavender", "peach", "lemon yellow", "lilac"
            ],
            "bright": [
                "bright red", "hot pink", "electric blue", "neon green",
                "bright yellow", "vibrant orange", "magenta"
            ],
            "patterns": [
                "multicolor", "two-tone", "color-blocked"
            ],
            "modifiers": ["light", "dark", "muted", "vibrant", "deep", "pale", "rich"]
        },
        
        "pattern": {
            # Visual patterns Qwen2-VL can generate
            "geometric": [
                "striped", "horizontal stripes", "vertical stripes",
                "checkered", "gingham", "plaid", "tartan",
                "polka dot", "small polka dots", "large polka dots",
                "chevron", "zigzag", "geometric print", "houndstooth",
                "argyle", "grid pattern", "diamond pattern"
            ],
            "organic": [
                "floral print", "small floral", "large floral", "rose print",
                "paisley", "animal print", "leopard print", "zebra print",
                "snake print", "camouflage", "camo print",
                "abstract floral", "tropical print", "leaf print"
            ],
            "abstract": [
                "tie-dye", "ombre", "gradient", "abstract print",
                "watercolor print", "marble print", "splatter print",
                "color block", "graphic print"
            ],
            "minimal": [
                "solid color", "plain", "no pattern", "textured solid"
            ]
        },
        
        "surface_detail": {
            # Texture details Qwen2-VL can render
            "fabric_texture": [
                "ribbed", "cable knit", "waffle knit", "herringbone",
                "twill", "corduroy", "velvet", "velour", "fleece",
                "terry cloth", "bouclé", "jacquard"
            ],
            "embellishments": [
                "embroidered", "sequined", "beaded", "studded",
                "lace trim", "lace overlay", "mesh panels",
                "cutout details", "ruffled", "pleated", "gathered",
                "smocked", "quilted", "patchwork"
            ],
            "hardware": [
                "zip front", "zipper", "buttons", "button-down",
                "snap closure", "drawstring", "elastic waist",
                "belt loops", "pockets"
            ]
        }
    },
    
    # 2. FIT & SILHOUETTE (How garment sits on body)
    "fit": {
        "overall_fit": [
            "skin-tight", "tight", "fitted", "slim fit", "tailored",
            "regular fit", "standard fit", "relaxed fit", "loose fit",
            "oversized", "baggy", "flowy", "boxy", "slouchy"
        ],
        "length": {
            "tops": [
                "cropped", "crop top length", "waist length",
                "hip length", "regular length", "tunic length", "longline"
            ],
            "bottoms": [
                "micro mini", "mini", "above knee", "knee-length",
                "midi", "below knee", "ankle-length", "floor-length", "maxi"
            ],
            "sleeves": [
                "sleeveless", "cap sleeve", "short sleeve", 
                "elbow length", "3/4 sleeve", "long sleeve", "extra long sleeve"
            ],
            "pants_length": [
                "shorts", "bermuda", "cropped", "ankle-length", "full-length"
            ]
        },
        "neckline": [
            "crew neck", "V-neck", "deep V-neck", "scoop neck",
            "boat neck", "off-shoulder", "one-shoulder", "strapless",
            "halter neck", "high neck", "turtleneck", "cowl neck",
            "square neck", "sweetheart", "collar", "button-up collar"
        ],
        "waist": [
            "high-waisted", "high-rise", "mid-rise", "low-rise",
            "dropped waist", "empire waist", "natural waist", "elasticated waist"
        ],
        "cut_style": [
            "A-line", "bodycon", "shift", "wrap style", "asymmetric",
            "straight cut", "tapered", "wide leg", "flared", "bootcut",
            "skinny", "relaxed", "boyfriend fit", "mom fit"
        ]
    },
    
    # 3. VISUAL COMPOSITION (What VLM sees in image)
    "observed_elements": {
        "current_garment": [
            # VLM fills these based on what it sees
            "describe current garment type",
            "describe current color",
            "describe current fit",
            "describe current pattern"
        ],
        "body_characteristics": [
            "slim build", "athletic build", "curvy build", "plus-size",
            "petite frame", "tall frame", "average build", "muscular"
        ],
        "skin_tone": [
            "fair skin", "light skin", "medium skin", "tan skin",
            "olive skin", "brown skin", "dark skin", "deep skin tone"
        ],
        "pose_type": [
            "standing straight", "standing casually", "arms at sides",
            "hands in pockets", "arms crossed", "one hand on hip",
            "hands clasped", "arms raised", "turned slightly",
            "walking", "sitting", "leaning", "posed"
        ],
        "camera_view": [
            "front view", "front-facing", "facing camera",
            "side view", "profile view", "three-quarter view",
            "back view", "angled view", "turned body"
        ],
        "visible_elements": [
            "full body visible", "upper body visible", "torso visible",
            "head cropped", "legs visible", "arms visible"
        ]
    },
    
    # 4. SCENE CONTEXT (Preserve these)
    "scene": {
        "background": [
            "plain white background", "solid gray background", "solid color background",
            "studio background", "indoor setting", "room interior",
            "outdoor setting", "street scene", "natural setting",
            "blurred background", "bokeh background", "minimal background"
        ],
        "lighting": [
            "soft natural lighting", "bright natural light", "window light",
            "studio lighting", "even lighting", "front lighting",
            "side lighting", "dramatic lighting", "golden hour lighting",
            "overcast light", "indirect lighting", "well-lit"
        ],
        "image_quality": [
            "high resolution", "sharp focus", "clear image",
            "professional photography", "clean image", "detailed"
        ]
    },
    
    # 5. EDITING INSTRUCTIONS (Qwen2-VL specific)
    "editing_actions": {
        "primary_verbs": [
            "change", "replace", "transform", "convert", "modify",
            "update", "switch", "alter"
        ],
        "preservation_verbs": [
            "keep", "maintain", "preserve", "retain", "don't change"
        ],
        "target_specification": [
            "the {garment_type}",
            "the current {garment_type}",
            "this {garment_type}",
            "their {garment_type}"
        ],
        "result_specification": [
            "into a {description}",
            "to a {description}",
            "with a {description}"
        ]
    },
    
    # 6. STYLE & AESTHETIC (Context for coherence)
    "style_context": {
        "aesthetic": [
            "casual", "formal", "business casual", "smart casual",
            "athletic", "sporty", "streetwear", "urban",
            "bohemian", "boho", "minimalist", "classic",
            "trendy", "vintage", "retro", "preppy",
            "edgy", "elegant", "sophisticated", "relaxed"
        ],
        "occasion": [
            "everyday wear", "casual outing", "work attire",
            "formal event", "party wear", "loungewear",
            "activewear", "beach wear", "summer outfit"
        ],
        "season": [
            "summer", "spring", "fall", "autumn", "winter", "all-season"
        ]
    },
    
    # 7. DETAIL LEVEL (Prompt complexity control)
    "complexity": {
        "simple": {
            "example": "Change the {current} to a {color} {garment_type}",
            "attributes": ["garment_type", "color"]
        },
        "moderate": {
            "example": "Replace the {current} with a {color} {material} {garment_type} with {fit} fit",
            "attributes": ["garment_type", "color", "material", "fit"]
        },
        "detailed": {
            "example": "Transform the {current} into a {color} {material} {garment_type} with {pattern}. The garment should have {fit} fit, {length}, and {neckline}",
            "attributes": ["garment_type", "color", "material", "pattern", "fit", "length", "neckline"]
        },
        "comprehensive": {
            "example": "Change the {current} to a {color_modifier} {color} {material} {garment_type} featuring {pattern}. It should have {fit} fit with {length} and {neckline}. The fabric should be {texture} with {surface_detail}. Maintain the {pose}, {lighting}, and {background}",
            "attributes": ["all_relevant"]
        }
    }
}
