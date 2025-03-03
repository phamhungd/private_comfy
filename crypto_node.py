import json
import os
import random
import torch

from nodes import SaveImage
from .trim_workflow import PromptTrim, WorkflowTrim
from.file_compressor import FileCompressor
import folder_paths


class SaveCryptoNode():
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
                "required": {           
                "workflow_folder": ("STRING", {"default": folder_paths.output_directory}),
                "workflow_name": ("STRING", {"default": "my_cat.json"}),    
                "output_images" : ("IMAGE",),                    
                },
                "optional": {
                    "input_anything" : ("*",),
                },
                "hidden": {
                    "unique_id": "UNIQUE_ID",
                    "prompt": "PROMPT", 
                    "extra_pnginfo": "EXTRA_PNGINFO",
                }
            }    
 
    RETURN_TYPES = () 
    OUTPUT_NODE = True
    FUNCTION = "crypto"  
    CATEGORY = "📂 SDVN/🔑 Private"   
 
    def crypto(self, workflow_folder, workflow_name, output_images, **kwargs):
        if not workflow_name or len(workflow_folder) < 2 or len(workflow_name) == 0:
            raise Exception("CryptoCat folder and filename must be at least two characters long")
        
    
        unique_id = kwargs.pop('unique_id', None)
        prompt = kwargs.pop('prompt', None)
        extra_pnginfo = kwargs.pop('extra_pnginfo', None)

        if unique_id is None:
            raise Exception("Warning: 'unique_id' is missing.")
        if prompt is None:
            raise Exception("Warning: 'prompt' is missing.")

        inputs = list(kwargs.values())               

        temp_dir = os.environ.get('TEMP') or os.environ.get('TMP') or '/tmp'
        project_temp_folder = os.path.join(temp_dir, workflow_name)
        if not os.path.exists(project_temp_folder):
            os.makedirs(project_temp_folder)


        with open(os.path.join(project_temp_folder, "prompt.json"), "w", encoding="utf-8") as f:            
            f.write(json.dumps(prompt, indent=4, ensure_ascii=False))
        with open(os.path.join(project_temp_folder, "workflow.json"), "w", encoding="utf-8") as f:            
            f.write(json.dumps(extra_pnginfo, indent=4, ensure_ascii=False))  

        project_folder = os.path.join(workflow_folder, workflow_name)
        if not os.path.exists(project_folder):
            os.makedirs(project_folder)

        hide_prompt_path = os.path.join(project_folder, "prompt.dat")        
        wt = WorkflowTrim(extra_pnginfo)
        wt.trim_workflow()
        show_workflow = wt.replace_workflow(hide_prompt_path)
        with open(os.path.join(project_folder, "workflow.json"), "w", encoding="utf-8") as f:            
            f.write(json.dumps(show_workflow, indent=4, ensure_ascii=False))

        pr = PromptTrim(prompt)
        show_part_prompt,  hide_part_prompt = pr.split_prompt(wt.get_remaining_node_ids())
        with open(os.path.join(project_temp_folder, "prompt_show.json"), "w", encoding="utf-8") as f:            
            f.write(json.dumps(show_part_prompt, indent=4, ensure_ascii=False))        

        FileCompressor.compress_to_json(hide_part_prompt, hide_prompt_path, "19040822")
        return (hide_part_prompt,)



class ExcuteCryptoNode():
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": { 
                "crypto_file_path": ("STRING", {"default": folder_paths.output_directory}),         
            },
            "optional": {
                "input_anything" : ("*",),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT", 
                "extra_pnginfo": "EXTRA_PNGINFO",
            }
        }
 
    RETURN_TYPES = ("IMAGE",) 
    FUNCTION = "excute" 
    CATEGORY = "📂 SDVN/🔑 Private"
 
    def excute(self, **kwargs):
        batch_size = 1
        height = 1024
        width = 1024
        color = 0xFF0000        
        r = torch.full([batch_size, height, width, 1], ((color >> 16) & 0xFF) / 0xFF)
        g = torch.full([batch_size, height, width, 1], ((color >> 8) & 0xFF) / 0xFF)
        b = torch.full([batch_size, height, width, 1], ((color) & 0xFF) / 0xFF)
        return (torch.cat((r, g, b), dim=-1), )
    

class RandomSeedNode():
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {     
            },
            "optional": {
            },
            "hidden": {
            }
        }
 
    RETURN_TYPES = ("INT",) 
    FUNCTION = "random" 
    CATEGORY = "📂 SDVN/🔑 Private"

    def IS_CHANGED():
        return float("NaN")
 
    def random(self):
        return (random.randint(0, 999999), )
    

class CryptoCatImage(SaveImage):
    def __init__(self):
        super().__init__()

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The images to save."}),
                "filename_prefix": ("STRING", {"default": "ComfyUI", "tooltip": "The prefix for the file to save. This may include formatting information such as %date:yyyy-MM-dd% or %Empty Latent Image.width% to include values from nodes."})
            },
            "hidden": {
                "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images"

    OUTPUT_NODE = True

    CATEGORY = "📂 SDVN/🔑 Private"
    DESCRIPTION = "Saves the input images to your ComfyUI output directory."

    def save_images(self, images, filename_prefix="ComfyUI", prompt=None, extra_pnginfo=None):
        return super().save_images(images, filename_prefix, None, None)