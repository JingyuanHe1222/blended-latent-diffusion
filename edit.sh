
#!/bin/bash

# object=flower
# mask_object=""


python scripts/text_editing_stable_diffusion.py --prompt "a stone" --init_image "inputs/img.png" --mask "inputs/mask.png" --output_path "outputs/mask/b_a_stone.png"