
#!/bin/bash

# object=flower
# mask_object=""


python scripts/text_editing_stable_diffusion.py --prompt "dog" --init_image "inputs/cat_2.jpg" --mask "inputs/mask_cat_2_cat.png" --output_path "outputs/cat_2_dog.png" --morph True