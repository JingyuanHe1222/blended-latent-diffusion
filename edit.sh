
#!/bin/bash

# object=flower
# mask_object=""


python scripts/text_editing_stable_diffusion.py --prompt "cat" --init_image "inputs/woman_and_dog.jpg" --mask "inputs/mask_woman_and_dog_dog.png" --output_path "outputs/woman_and_dog_cat.jpg" --morph True