
#!/bin/bash

# object=flower
# mask_object=""


python scripts/text_editing_stable_diffusion.py --prompt "flower" --init_image "inputs/img.png" --mask "inputs/mask_grey_cat.png" --output_path "outputs/mask/erode_dia_flower_grey_cat.png" --morph True