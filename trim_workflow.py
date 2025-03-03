import copy
import os
import random
import sys
import folder_paths
import json
from .file_compressor import FileCompressor


class WorkflowTrim:
    def __init__(self, workflow):
        if "workflow" in workflow:
            self.workflow = copy.deepcopy(workflow["workflow"])
        else:
            self.workflow = copy.deepcopy(workflow)

        self.output_images_link = 0

        nodes_dict = {node["id"]: node for node in self.workflow["nodes"]}
        self.max_id_index = max(nodes_dict.keys()) + 1

    @staticmethod
    def find_workflow_related_nodes(nodes, input_ids):
        found_ids = set()
        stack = list(input_ids)
        while stack:
            link_id = stack.pop()
            for node_id, node in nodes.items():
                outputs = node.get("outputs", None)
                if not outputs:
                    continue
                for output in outputs:
                    links = output.get("links", None)
                    if not links:
                        continue
                    if link_id in links:
                        if node_id not in found_ids:
                            found_ids.add(node_id)
                            inputs = node.get("inputs", [])
                            for input_node in inputs:
                                link_id = input_node.get("link")
                                if link_id is not None:
                                    stack.append(link_id)
                        break
        return found_ids

    def trim_workflow(self):
        if not self.workflow:
            raise ValueError("Invalid JSON format.")

        nodes_dict = {node["id"]: node for node in self.workflow["nodes"]}
        save_crypto_node_ids = [
            node_id
            for node_id, details in nodes_dict.items()
            if details.get("type") == "SaveCryptoNode"
        ]
        if len(save_crypto_node_ids) == 1:
            save_crypto_node_id = save_crypto_node_ids[0]

            input_ids = set()
            for input_node in nodes_dict[save_crypto_node_id].get("inputs", []):
                if input_node["name"] and input_node["name"].startswith(
                    "input_anything"
                ):
                    input_ids.add(input_node["link"])
                if input_node["name"] and input_node["name"] == "output_images":
                    self.output_images_link = input_node["link"]

            input_ids = {link_id for link_id in input_ids if link_id is not None}

            related_node_ids = self.find_workflow_related_nodes(nodes_dict, input_ids)

            related_node_ids.add(save_crypto_node_id)

            self.workflow["nodes"] = [
                details
                for node_id, details in nodes_dict.items()
                if node_id in related_node_ids
            ]
            remaining_node_ids = {node["id"] for node in self.workflow["nodes"]}
            self.workflow.pop("groups", None)
            self.workflow["output_images_id"] = self.output_images_link

            self.workflow["links"] = [
                link
                for link in self.workflow["links"]
                if link[1] in remaining_node_ids and link[3] in remaining_node_ids
            ]

            return self.workflow

        elif len(save_crypto_node_ids) > 1:
            raise ValueError("Error: Multiple 'SaveCryptoNode' instances found.")
        else:
            raise ValueError("Error: No 'SaveCryptoNode' instances found.")

    def replace_workflow(self, hide_prompt_path):
        if not self.workflow:
            raise ValueError("Invalid JSON format.")

        nodes_dict = {node["id"]: node for node in self.workflow["nodes"]}
        output_images_link = None

        for node in self.workflow["nodes"]:
            if node.get("type") == "SaveCryptoNode":
                node["type"] = "ExcuteCryptoNode"
                node["properties"]["Node name for S&R"] = "ExcuteCryptoNode"

                for inp in node["inputs"]:
                    if inp["name"] == "output_images":
                        output_images_link = inp.get("link")
                node["inputs"] = [
                    inp for inp in node["inputs"] if inp["name"] != "output_images"
                ]
                node["widgets_values"] = [hide_prompt_path]

        execute_node = next(
            (
                node
                for node in self.workflow["nodes"]
                if node.get("type") == "ExcuteCryptoNode"
            ),
            None,
        )

        if not execute_node:
            raise ValueError("No 'ExcuteCryptoNode' instance found.")

        execute_node_pos = execute_node["pos"]
        self.max_id_index = max(max(nodes_dict.keys()) + 1, self.max_id_index)
        new_save_image_node = {
            "id": self.max_id_index,
            "type": "CryptoCatImage",
            "size": {"0": 210, "1": 162},
            "flags": {},
            "order": 50,
            "mode": 0,
            "inputs": [
                {
                    "name": "images",
                    "type": "IMAGE",
                    "link": output_images_link,
                    "label": "images",
                }
            ],
            "outputs": [],
            "properties": {"Node name for S&R": "CryptoCatImage"},
        }

        self.workflow["nodes"].append(new_save_image_node)

        self.workflow["links"] = [
            link for link in self.workflow["links"] if link[0] != output_images_link
        ]

        execute_node["outputs"] = [
            {
                "name": "IMAGE",
                "type": "IMAGE",
                "links": [output_images_link],
                "shape": 3,
                "label": "IMAGE",
                "slot_index": 0,
            }
        ]

        self.workflow["links"].append(
            [
                output_images_link,
                execute_node["id"],
                0,
                new_save_image_node["id"],
                0,
                "IMAGE",
            ]
        )

        return self.workflow

    def set_excute_crypto_node_path(self, path):
        if not self.workflow:
            raise ValueError("Invalid JSON format.")
        for node in self.workflow["nodes"]:
            if node.get("type") == "ExcuteCryptoNode":
                node["properties"]["Path to executable file"] = path

    def get_remaining_node_ids(self):
        if not self.workflow:
            raise ValueError("Invalid JSON format.")
        remaining_node_ids = {node["id"] for node in self.workflow["nodes"]}
        return remaining_node_ids


class PromptTrim:
    def __init__(self, prompt):
        self.prompt = prompt
        self.debug = True
        self.hide_part_prompt = {}
        self.show_part_prompt = {}

    def split_prompt(self, related_node_ids):
        if not self.prompt:
            raise ValueError("Invalid JSON format.")

        save_crypto_node_id = None
        output_images_ids = []
        for node_id, details in self.prompt.items():
            if details["class_type"] == "SaveCryptoNode":
                output_images_ids = details["inputs"].get("output_images")
                save_crypto_node_id = int(node_id)
                break

        if save_crypto_node_id is None:
            raise ValueError("Error: No 'SaveCryptoNode' instances found.")

        if save_crypto_node_id not in related_node_ids:
            raise AssertionError("SaveCryptoNode not found in related node list.")

        self.hide_part_prompt = {}
        self.show_part_prompt = {}

        for node_id in self.prompt.keys():
            node_id_int = int(node_id)
            if node_id_int not in related_node_ids:
                self.hide_part_prompt[node_id_int] = self.prompt[node_id]
            else:
                self.show_part_prompt[node_id_int] = self.prompt[node_id]

        self.hide_part_prompt["output_images_ids"] = output_images_ids
        return self.show_part_prompt, self.hide_part_prompt

    def replace_prompt(self):
        if not self.prompt:
            raise ValueError("Invalid JSON format.")

        dat_path = ""
        excute_crypto_id = None

        for node_id, node in list(self.prompt.items()):
            if node.get("class_type") == "ExcuteCryptoNode":
                dat_path = node["inputs"].get("dat_path")
                excute_crypto_id = node_id

                del self.prompt[node_id]
                break

        if not dat_path:
            print("No 'ExcuteCryptoNode' found in prompt.")
            return self.prompt

        inject_json = FileCompressor.decompress_from_json(dat_path, "sdvn")
        output_images_ids = inject_json["output_images_ids"]
        inject_json.pop("output_images_ids", None)
        for node_id, node in list(self.prompt.items()):
            if node.get("class_type") == "CryptoCatImage":
                ids = node["inputs"]["images"]
                if excute_crypto_id in ids:
                    node["inputs"]["images"] = output_images_ids

        random_seed_node = next(
            (
                node
                for node in inject_json.values()
                if node.get("class_type") == "RandomSeedNode"
            ),
            None,
        )
        if random_seed_node:
            random_seed_node["inputs"]["is_changed"] = random.randint(0, 999999)

        self.prompt.update(inject_json)

        if self.debug == True:
            temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp"
            filename = os.path.basename(dat_path) + "_prompt.json"
            with open(os.path.join(temp_dir, filename), "w", encoding="utf-8") as f:
                json.dump(self.prompt, f, indent=4)
            print(f"prompt len = {len(self.prompt)}")

        return self.prompt

    def has_crypto_node(self):
        if not self.prompt:
            return False
        return any(
            node.get("class_type") == "ExcuteCryptoNode"
            for node in self.prompt.values()
        )