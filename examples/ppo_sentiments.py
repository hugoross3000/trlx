# Generates positive movie reviews by tuning a pretrained model on IMDB dataset
# with a sentiment reward function

import os
import pathlib
from typing import List

import torch
import yaml
from datasets import load_dataset
from transformers import pipeline

import trlx
from trlx.data.configs import TRLConfig


def get_positive_score(scores):
    "Extract value associated with a positive sentiment from pipeline's output"
    return dict(map(lambda x: tuple(x.values()), scores))["POSITIVE"]


def main(hparams={}):
    default_config = hparams.pop("default_config")
    config = TRLConfig.update(default_config, hparams)

    device = os.environ.get("ACCELERATE_TORCH_DEVICE", None)
    if device is None:
        if torch.cuda.is_available():
            device = int(os.environ.get("LOCAL_RANK", 0))
        else:
            device = -1

    sentiment_fn = pipeline(
        "sentiment-analysis",
        "lvwerra/distilbert-imdb",
        top_k=2,
        truncation=True,
        batch_size=256,
        device=device,
    )

    def reward_fn(samples: List[str], **kwargs) -> List[float]:
        sentiments = list(map(get_positive_score, sentiment_fn(samples)))
        return sentiments

    # Take few words off of movies reviews as prompts
    imdb = load_dataset("imdb", split="train+test")
    prompts = [" ".join(review.split()[:4]) for review in imdb["text"]]

    trlx.train(
        reward_fn=reward_fn,
        prompts=prompts,
        eval_prompts=["I don't know much about Hungarian underground"] * 256,
        config=config,
    )


if __name__ == "__main__":
    config_path = pathlib.Path(__file__).parent.joinpath("../configs/ppo_config.yml")
    with config_path.open() as f:
        default_config = yaml.safe_load(f)
    main({"default_config": default_config})
