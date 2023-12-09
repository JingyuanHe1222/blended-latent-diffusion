
#!/bin/bash

# object=flower
# mask_object=""


python scripts/text_editing_stable_diffusion.py --prompt "basketball" --init_image "inputs/img.png" --mask "inputs/mask.png" --output_path "outputs/img_basketball_without.jpg" --morph False