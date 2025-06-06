# Copyright (c) 2023, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

from sdp.processors.base_processor import BaseProcessor


def load_manifest(manifest: Path) -> List[Dict[str, Union[str, float]]]:
    result = []
    with manifest.open() as f:
        for i, line in enumerate(f):
            data = json.loads(line)
            result.append(data)
    return result


class PCInference(BaseProcessor):
    """Adds predictions of a text-based punctuation and capitalization (P&C) model.

    Operates on the text in the ``input_text_field``, and saves predictions in
    the ``output_text_field``.

    Args:
        input_text_field (str): the text field that will be the input to the P&C model.
        output_text_field (str): the text field where the output of the PC model
            will be saved.
        batch_size (int): the batch sized used by the P&C model.
        device (str, Optional): the device used by the P&C model. Can be skipped to auto-select.
        pretrained_name (str, Optional): the pretrained_name of the P&C model.
        model_path (str, Optional): the model path to the P&C model.
        **kwargs: Additional keyword arguments to be passed to the base class `PCInference`.

    .. note::
        Either ``pretrained_name`` or ``model_path`` have to be specified.

    Returns:
         The same data as in the input manifest with an additional field
         <output_text_field> containing P&C model's predictions.
    """

    def __init__(
        self,
        input_text_field: str,
        output_text_field: str,
        batch_size: int,
        device: Optional[str] = None,
        pretrained_name: Optional[str] = None,
        model_path: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.pretrained_name = pretrained_name
        self.model_path = model_path
        self.input_text_field = input_text_field
        self.output_text_field = output_text_field
        self.device = device
        self.batch_size = batch_size

        # verify self.pretrained_name/model_path
        if self.pretrained_name is None and self.model_path is None:
            raise ValueError("pretrained_name and model_path cannot both be None")
        if self.pretrained_name is not None and self.model_path is not None:
            raise ValueError("pretrained_name and model_path cannot both be specified")

    def process(self):
        import torch  # importing after nemo to make sure users first install nemo, instead of torch, then nemo
        from nemo.collections.nlp.models import PunctuationCapitalizationModel

        if self.pretrained_name:
            model = PunctuationCapitalizationModel.from_pretrained(self.pretrained_name)
        else:
            model = PunctuationCapitalizationModel.restore_from(self.model_path)

        if self.device is None:
            if torch.cuda.is_available():
                model = model.cuda()
            else:
                model = model.cpu()
        else:
            model = model.to(self.device)

        manifest = load_manifest(Path(self.input_manifest_file))

        texts = []
        for item in manifest:
            texts.append(item[self.input_text_field])

        processed_texts = model.add_punctuation_capitalization(
            texts,
            batch_size=self.batch_size,
        )
        Path(self.output_manifest_file).parent.mkdir(exist_ok=True, parents=True)
        with Path(self.output_manifest_file).open('w') as f:
            for item, t in zip(manifest, processed_texts):
                item[self.output_text_field] = t
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
