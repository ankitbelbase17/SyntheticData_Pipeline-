VTON_DICTIONARY = {
    # 1. GARMENT ATTRIBUTES (Primary editing targets)
    "garment": {
        "prob": 0.28,  # Adjusted for normalization
        "type": {
            "prob": 1.0,  # Always pick a type
            "tops": {
                "prob": 0.4,
                "keywords": [
                    ("t-shirt", 0.22), ("blouse", 0.10), ("sweater", 0.09), ("tank top", 0.07), ("crop top", 0.06),
                    ("hoodie", 0.10), ("cardigan", 0.06), ("blazer", 0.05), ("button-up shirt", 0.08), ("polo shirt", 0.05),
                    ("turtleneck", 0.03), ("henley", 0.03), ("camisole", 0.02), ("tube top", 0.02), ("halter top", 0.02)
                ]
            },
            "bottoms": {
                "prob": 0.3,
                "keywords": [
                    ("jeans", 0.25), ("trousers", 0.13), ("shorts", 0.13), ("skirt", 0.10), ("leggings", 0.10),
                    ("joggers", 0.08), ("chinos", 0.05), ("cargo pants", 0.05), ("palazzo pants", 0.03),
                    ("culottes", 0.02), ("capris", 0.02), ("sweatpants", 0.04), ("pleated skirt", 0.03)
                ]
            },
            "dresses": {
                "prob": 0.12,
                "keywords": [
                    ("maxi dress", 0.15), ("midi dress", 0.18), ("mini dress", 0.18), ("sundress", 0.10),
                    ("cocktail dress", 0.10), ("shirt dress", 0.08), ("wrap dress", 0.08), ("A-line dress", 0.08),
                    ("bodycon dress", 0.07), ("slip dress", 0.04), ("sweater dress", 0.04)
                ]
            },
            "outerwear": {
                "prob": 0.13,
                "keywords": [
                    ("jacket", 0.18), ("coat", 0.13), ("parka", 0.05), ("trench coat", 0.07), ("bomber jacket", 0.08),
                    ("denim jacket", 0.10), ("leather jacket", 0.10), ("windbreaker", 0.06), ("vest", 0.05),
                    ("peacoat", 0.05), ("blazer", 0.07), ("kimono", 0.03), ("poncho", 0.03)
                ]
            },
            "full_body": {
                "prob": 0.05,
                "keywords": [
                    ("jumpsuit", 0.30), ("romper", 0.20), ("overall", 0.15), ("bodysuit", 0.15), ("tracksuit", 0.10), ("onesie", 0.10)
                ]
            }
        },
        
        "material": {
            "prob": 0.15,
            "cotton": {"prob": 0.30, "keywords": [("soft cotton", 0.4), ("thick cotton", 0.2), ("cotton jersey", 0.3), ("organic cotton", 0.1)]},
            "denim": {"prob": 0.15, "keywords": [("light denim", 0.3), ("dark denim", 0.3), ("stretch denim", 0.2), ("rigid denim", 0.2)]},
            "knit": {"prob": 0.13, "keywords": [("chunky knit", 0.3), ("fine knit", 0.3), ("ribbed knit", 0.2), ("cable knit", 0.2)]},
            "silk": {"prob": 0.07, "keywords": [("smooth silk", 0.4), ("silk satin", 0.3), ("raw silk", 0.2), ("silk charmeuse", 0.1)]},
            "wool": {"prob": 0.10, "keywords": [("merino wool", 0.3), ("wool blend", 0.3), ("cashmere", 0.2), ("fleece", 0.2)]},
            "synthetic": {"prob": 0.15, "keywords": [("polyester", 0.4), ("nylon", 0.3), ("spandex blend", 0.2), ("jersey knit", 0.1)]},
            "leather": {"prob": 0.05, "keywords": [("genuine leather", 0.4), ("faux leather", 0.3), ("suede", 0.2), ("patent leather", 0.1)]},
            "linen": {"prob": 0.05, "keywords": [("crisp linen", 0.5), ("wrinkled linen", 0.3), ("linen blend", 0.2)]},
            "texture_keywords": {"prob": 0.1, "keywords": [
                ("smooth", 0.15), ("textured", 0.15), ("soft", 0.15), ("stiff", 0.10), ("stretchy", 0.10),
                ("structured", 0.10), ("flowy", 0.10), ("crisp", 0.05), ("plush", 0.05), ("sleek", 0.05)
            ]}
        },
        
        "color": {
            "prob": 0.08,
            "neutrals": {"prob": 0.45, "keywords": [
                ("white", 0.13), ("off-white", 0.07), ("cream", 0.07), ("beige", 0.07), ("tan", 0.07), ("camel", 0.05),
                ("black", 0.18), ("charcoal", 0.07), ("gray", 0.09), ("light gray", 0.07), ("dark gray", 0.07),
                ("navy", 0.06), ("navy blue", 0.03), ("brown", 0.03), ("chocolate brown", 0.02), ("taupe", 0.02)
            ]},
            "warm": {"prob": 0.18, "keywords": [
                ("red", 0.15), ("crimson", 0.08), ("burgundy", 0.08), ("maroon", 0.08), ("wine red", 0.06),
                ("orange", 0.10), ("burnt orange", 0.08), ("coral", 0.08), ("rust", 0.07), ("terracotta", 0.07),
                ("yellow", 0.10), ("mustard yellow", 0.07), ("golden yellow", 0.04), ("ochre", 0.04)
            ]},
            "cool": {"prob": 0.22, "keywords": [
                ("blue", 0.13), ("royal blue", 0.07), ("cobalt", 0.07), ("sky blue", 0.07), ("powder blue", 0.07),
                ("green", 0.13), ("forest green", 0.07), ("emerald", 0.07), ("olive", 0.07), ("sage green", 0.07),
                ("purple", 0.07), ("lavender", 0.04), ("plum", 0.03), ("violet", 0.03), ("indigo", 0.03),
                ("teal", 0.03), ("turquoise", 0.03), ("aqua", 0.03), ("mint", 0.03)
            ]},
            "pastels": {"prob": 0.07, "keywords": [
                ("pastel pink", 0.18), ("blush pink", 0.18), ("baby blue", 0.18), ("mint green", 0.18),
                ("lavender", 0.10), ("peach", 0.07), ("lemon yellow", 0.06), ("lilac", 0.05)
            ]},
            "bright": {"prob": 0.05, "keywords": [
                ("bright red", 0.20), ("hot pink", 0.20), ("electric blue", 0.20), ("neon green", 0.15),
                ("bright yellow", 0.10), ("vibrant orange", 0.10), ("magenta", 0.05)
            ]},
            "patterns": {"prob": 0.02, "keywords": [
                ("multicolor", 0.5), ("two-tone", 0.3), ("color-blocked", 0.2)
            ]},
            "modifiers": {"prob": 0.01, "keywords": [
                ("light", 0.2), ("dark", 0.2), ("muted", 0.2), ("vibrant", 0.15), ("deep", 0.1), ("pale", 0.1), ("rich", 0.05)
            ]}
        },
        
        "pattern": {
            "prob": 0.10,
            "geometric": {"prob": 0.35, "keywords": [
                ("striped", 0.15), ("horizontal stripes", 0.10), ("vertical stripes", 0.10),
                ("checkered", 0.10), ("gingham", 0.08), ("plaid", 0.10), ("tartan", 0.07),
                ("polka dot", 0.08), ("small polka dots", 0.05), ("large polka dots", 0.05),
                ("chevron", 0.04), ("zigzag", 0.03), ("geometric print", 0.03), ("houndstooth", 0.01),
                ("argyle", 0.01), ("grid pattern", 0.01), ("diamond pattern", 0.01)
            ]},
            "organic": {"prob": 0.35, "keywords": [
                ("floral print", 0.15), ("small floral", 0.10), ("large floral", 0.10), ("rose print", 0.08),
                ("paisley", 0.07), ("animal print", 0.10), ("leopard print", 0.10), ("zebra print", 0.05),
                ("snake print", 0.05), ("camouflage", 0.05), ("camo print", 0.05),
                ("abstract floral", 0.05), ("tropical print", 0.03), ("leaf print", 0.02)
            ]},
            "abstract": {"prob": 0.20, "keywords": [
                ("tie-dye", 0.20), ("ombre", 0.15), ("gradient", 0.15), ("abstract print", 0.15),
                ("watercolor print", 0.10), ("marble print", 0.10), ("splatter print", 0.10),
                ("color block", 0.03), ("graphic print", 0.02)
            ]},
            "minimal": {"prob": 0.10, "keywords": [
                ("solid color", 0.40), ("plain", 0.30), ("no pattern", 0.20), ("textured solid", 0.10)
            ]}
        },
        
        "surface_detail": {
            "prob": 0.10,
            "fabric_texture": {"prob": 0.5, "keywords": [
                ("ribbed", 0.10), ("cable knit", 0.10), ("waffle knit", 0.10), ("herringbone", 0.10),
                ("twill", 0.10), ("corduroy", 0.10), ("velvet", 0.10), ("velour", 0.10), ("fleece", 0.10),
                ("terry cloth", 0.05), ("bouclé", 0.03), ("jacquard", 0.02)
            ]},
            "embellishments": {"prob": 0.3, "keywords": [
                ("embroidered", 0.15), ("sequined", 0.10), ("beaded", 0.10), ("studded", 0.10),
                ("lace trim", 0.10), ("lace overlay", 0.10), ("mesh panels", 0.10),
                ("cutout details", 0.10), ("ruffled", 0.05), ("pleated", 0.05), ("gathered", 0.03),
                ("smocked", 0.01), ("quilted", 0.01), ("patchwork", 0.01)
            ]},
            "hardware": {"prob": 0.2, "keywords": [
                ("zip front", 0.15), ("zipper", 0.15), ("buttons", 0.15), ("button-down", 0.15),
                ("snap closure", 0.10), ("drawstring", 0.10), ("elastic waist", 0.10),
                ("belt loops", 0.05), ("pockets", 0.05)
            ]}
        }
    },
    
    # 2. FIT & SILHOUETTE (How garment sits on body)
    "fit": {
        "prob": 0.10,
        "overall_fit": {"prob": 0.3, "keywords": [
            ("regular fit", 0.18), ("standard fit", 0.12), ("fitted", 0.12), ("slim fit", 0.10), ("relaxed fit", 0.10),
            ("loose fit", 0.08), ("oversized", 0.07), ("tight", 0.06), ("skin-tight", 0.03), ("baggy", 0.04),
            ("flowy", 0.03), ("boxy", 0.03), ("slouchy", 0.02), ("tailored", 0.02)
        ]},
        "length": {"prob": 0.25,
            "tops": {"prob": 0.5, "keywords": [
                ("regular length", 0.25), ("waist length", 0.18), ("hip length", 0.18), ("cropped", 0.10), ("crop top length", 0.07),
                ("tunic length", 0.12), ("longline", 0.10)
            ]},
            "bottoms": {"prob": 0.3, "keywords": [
                ("ankle-length", 0.20), ("full-length", 0.18), ("midi", 0.15), ("knee-length", 0.13), ("mini", 0.10),
                ("above knee", 0.08), ("below knee", 0.07), ("micro mini", 0.05), ("floor-length", 0.04), ("maxi", 0.03)
            ]},
            "sleeves": {"prob": 0.15, "keywords": [
                ("short sleeve", 0.25), ("long sleeve", 0.25), ("sleeveless", 0.15), ("elbow length", 0.10), ("3/4 sleeve", 0.10),
                ("cap sleeve", 0.08), ("extra long sleeve", 0.07)
            ]},
            "pants_length": {"prob": 0.05, "keywords": [
                ("full-length", 0.35), ("ankle-length", 0.25), ("cropped", 0.15), ("shorts", 0.15), ("bermuda", 0.10)
            ]}
        },
        "neckline": {"prob": 0.15, "keywords": [
            ("crew neck", 0.18), ("V-neck", 0.15), ("scoop neck", 0.10), ("high neck", 0.08), ("turtleneck", 0.08),
            ("square neck", 0.07), ("sweetheart", 0.07), ("collar", 0.07), ("button-up collar", 0.05), ("deep V-neck", 0.05),
            ("boat neck", 0.04), ("off-shoulder", 0.03), ("one-shoulder", 0.02), ("strapless", 0.01), ("halter neck", 0.01), ("cowl neck", 0.01)
        ]},
        "waist": {"prob": 0.08, "keywords": [
            ("mid-rise", 0.30), ("high-waisted", 0.25), ("high-rise", 0.15), ("natural waist", 0.10), ("low-rise", 0.08),
            ("dropped waist", 0.05), ("empire waist", 0.04), ("elasticated waist", 0.03)
        ]},
        "cut_style": {"prob": 0.07, "keywords": [
            ("straight cut", 0.18), ("A-line", 0.15), ("skinny", 0.12), ("relaxed", 0.10), ("wrap style", 0.08),
            ("shift", 0.07), ("tapered", 0.07), ("flared", 0.06), ("bootcut", 0.05), ("bodycon", 0.04),
            ("asymmetric", 0.03), ("boyfriend fit", 0.03), ("mom fit", 0.02)
        ]}
    },
    
    # 3. VISUAL COMPOSITION (What VLM sees in image)
    "observed_elements": {
        "prob": 0.30,
        "current_garment": {"prob": 0.12, "keywords": [
            ("describe current garment type", 0.25), ("describe current color", 0.25), ("describe current fit", 0.25), ("describe current pattern", 0.25)
        ]},
        "body_characteristics": {"prob": 0.15, "keywords": [
            ("average build", 0.18), ("slim build", 0.13), ("athletic build", 0.10), ("curvy build", 0.10), ("plus-size", 0.08),
            ("petite frame", 0.07), ("tall frame", 0.05), ("muscular", 0.05),
            ("prosthetic limb", 0.07), ("wheelchair user", 0.07), ("visible birthmark", 0.06), ("visible tattoo", 0.06),
            ("hijab", 0.04), ("turban", 0.03), ("hearing aid", 0.03)
        ]},
        "skin_tone": {"prob": 0.12, "keywords": [
            ("medium skin", 0.18), ("light skin", 0.15), ("fair skin", 0.13), ("tan skin", 0.13), ("olive skin", 0.10),
            ("brown skin", 0.10), ("dark skin", 0.10), ("deep skin tone", 0.08), ("albinism", 0.03)
        ]},
        "pose_type": {"prob": 0.15, "keywords": [
            ("standing straight", 0.13), ("standing casually", 0.12), ("arms at sides", 0.10), ("hands in pockets", 0.08), ("arms crossed", 0.07),
            ("one hand on hip", 0.07), ("hands clasped", 0.06), ("arms raised", 0.06), ("turned slightly", 0.06),
            ("walking", 0.06), ("sitting", 0.06), ("leaning", 0.04), ("posed", 0.03),
            ("crouching", 0.03), ("jumping", 0.03)
        ]},
        "camera_view": {"prob": 0.08, "keywords": [
            ("front view", 0.25), ("front-facing", 0.20), ("facing camera", 0.15), ("side view", 0.10), ("profile view", 0.10),
            ("three-quarter view", 0.08), ("back view", 0.05), ("angled view", 0.04), ("turned body", 0.03)
        ]},
        "visible_elements": {"prob": 0.08, "keywords": [
            ("full body visible", 0.30), ("upper body visible", 0.25), ("torso visible", 0.15), ("head cropped", 0.10), ("legs visible", 0.10), ("arms visible", 0.10)
        ]},
        "age_group": {"prob": 0.15, "keywords": [
            ("child", 0.18), ("teen", 0.18), ("young adult", 0.22), ("adult", 0.30), ("senior", 0.12)
        ]},
        "gender": {"prob": 0.12, "keywords": [
            ("male", 0.48), ("female", 0.48), ("non-binary", 0.04)
        ]},
        "body_shape": {"prob": 0.13, "keywords": [
            ("ectomorph", 0.25), ("mesomorph", 0.25), ("endomorph", 0.25), ("pear", 0.10), ("apple", 0.10), ("hourglass", 0.05)
        ]}
    },
    
    # 4. SCENE CONTEXT (Preserve these)
    "scene": {
        "prob": 0.08,
        "background": {"prob": 0.5, "keywords": [
            ("plain white background", 0.18), ("solid gray background", 0.10), ("solid color background", 0.10), ("studio background", 0.10), ("indoor setting", 0.10),
            ("room interior", 0.08), ("outdoor setting", 0.10), ("street scene", 0.08), ("natural setting", 0.08), ("blurred background", 0.04), ("bokeh background", 0.02), ("minimal background", 0.02)
        ]},
        "lighting": {"prob": 0.3, "keywords": [
            ("soft natural lighting", 0.18), ("bright natural light", 0.15), ("window light", 0.12), ("studio lighting", 0.12), ("even lighting", 0.10),
            ("front lighting", 0.08), ("side lighting", 0.08), ("dramatic lighting", 0.05), ("golden hour lighting", 0.05), ("overcast light", 0.04), ("indirect lighting", 0.02), ("well-lit", 0.01)
        ]},
        "image_quality": {"prob": 0.2, "keywords": [
            ("high resolution", 0.25), ("sharp focus", 0.20), ("clear image", 0.18), ("professional photography", 0.15), ("clean image", 0.12), ("detailed", 0.10)
        ]}
    },
    
    # 5. EDITING INSTRUCTIONS (Qwen2-VL specific)
    "editing_actions": {
        "prob": 0.08,
        "primary_verbs": {"prob": 0.4, "keywords": [
            ("change", 0.18), ("replace", 0.15), ("transform", 0.13), ("convert", 0.12), ("modify", 0.12), ("update", 0.10), ("switch", 0.10), ("alter", 0.10)
        ]},
        "preservation_verbs": {"prob": 0.2, "keywords": [
            ("keep", 0.25), ("maintain", 0.20), ("preserve", 0.20), ("retain", 0.20), ("don't change", 0.15)
        ]},
        "target_specification": {"prob": 0.2, "keywords": [
            ("the {garment_type}", 0.30), ("the current {garment_type}", 0.25), ("this {garment_type}", 0.25), ("their {garment_type}", 0.20)
        ]},
        "result_specification": {"prob": 0.2, "keywords": [
            ("into a {description}", 0.40), ("to a {description}", 0.35), ("with a {description}", 0.25)
        ]}
    },
    
    # 6. STYLE & AESTHETIC (Context for coherence)
    "style_context": {
        "prob": 0.08,
        "aesthetic": {"prob": 0.5, "keywords": [
            ("casual", 0.20), ("formal", 0.10), ("business casual", 0.08), ("smart casual", 0.08), ("athletic", 0.07), ("sporty", 0.07), ("streetwear", 0.07), ("urban", 0.05), ("bohemian", 0.05), ("boho", 0.04), ("minimalist", 0.04), ("classic", 0.04), ("trendy", 0.03), ("vintage", 0.02), ("retro", 0.01), ("preppy", 0.01), ("edgy", 0.01), ("elegant", 0.01), ("sophisticated", 0.01), ("relaxed", 0.01)
        ]},
        "occasion": {"prob": 0.3, "keywords": [
            ("everyday wear", 0.30), ("casual outing", 0.20), ("work attire", 0.15), ("formal event", 0.10), ("party wear", 0.10), ("loungewear", 0.05), ("activewear", 0.05), ("beach wear", 0.03), ("summer outfit", 0.02)
        ]},
        "season": {"prob": 0.2, "keywords": [
            ("summer", 0.25), ("spring", 0.20), ("fall", 0.18), ("autumn", 0.15), ("winter", 0.12), ("all-season", 0.10)
        ]}
    },
    
    # 7. DETAIL LEVEL (Prompt complexity control)
    "complexity": {
        "prob": 0.08,
        "simple": {"prob": 0.4, "example": "Change the {current} to a {color} {garment_type}", "attributes": ["garment_type", "color"]},
        "moderate": {"prob": 0.3, "example": "Replace the {current} with a {color} {material} {garment_type} with {fit} fit", "attributes": ["garment_type", "color", "material", "fit"]},
        "detailed": {"prob": 0.2, "example": "Transform the {current} into a {color} {material} {garment_type} with {pattern}. The garment should have {fit} fit, {length}, and {neckline}", "attributes": ["garment_type", "color", "material", "pattern", "fit", "length", "neckline"]},
        "comprehensive": {"prob": 0.1, "example": "Change the {current} to a {color_modifier} {color} {material} {garment_type} featuring {pattern}. It should have {fit} fit with {length} and {neckline}. The fabric should be {texture} with {surface_detail}. Maintain the {pose}, {lighting}, and {background}", "attributes": ["all_relevant"]}
    }
}
