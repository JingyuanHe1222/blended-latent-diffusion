
#!/bin/bash

# object=flower
# mask_object=""


python scripts/text_editing_stable_diffusion.py --prompt "dog" --init_image "inputs/dog_and_cat.jpg" --mask "inputs/mask_grey_cat.png" --output_path "outputs/mask/erode_dia_dog_dc.png" --morph True