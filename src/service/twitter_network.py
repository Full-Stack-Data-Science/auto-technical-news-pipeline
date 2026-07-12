from network.graph import build_nx_graph
from network.relation import *



INFLUENCERS =  [
    # Core AI / ML
    "karpathy", "ylecun", "AndrewYNg", "fchollet", "GoogleAI", "AIatMeta",
    "goodfellow_ian", "OriolVinyalsML", "demishassabis", "jeffdean",
    "ilyasut", "hardmaru", "lukaszkaiser", "quocleix", "sama", "kaifulee",
    "ID_AA_Carmack", "2morrowknight", "Scobleizer", "drfeifei", "KirkDBorne",
    "rowancheung", "antgrasso", "demishassabis", "Ronald_vanLoon", "TamaraMcCleary",
    "erikbryn", "timnitgebru", "oriolvinyalsml", "ceobillionaire", "soumithchintala",
    "waitin4agi_", "sallyeaves", "bernardmarr", "fabiomoioli", "pascal_bornet",
    "abhi1thakur", "iainljbrown", "HaroldSinnott", "ClaireSilver12", "TheTuringPost",
    "officiallogank",

    # GenAI / LLMs
    "OpenAI", "AnthropicAI", "GoogleDeepMind", "huggingface",
    "swyx", "gdb", "jerryjliu0", "GregKamradt",
    "simonw", "perplexity_ai", "togethercompute", "latentspacepod",
    "GroqInc", "Thom_Wolf",
    
    # Data engineering
    "seattledataguy", "Aurimas_Gr",

    # ML Engineering
    "jeremyphoward", "fastdotai", "rasbt", "seb_ruder", "chipro",
    "eugeneyan", "koenbok",

    # Data Science
    "hadleywickham", "KirkDBorne",
    "HilaryMason", "chrisalbon", "thomasp85", "drnic",

    # MLOps
    "hamelhusain", "wandb",
    "neptune_ai", "mlflow", "zenml_io",

    # Robotics / Vision / Hardware
    "lexfridman", "BostonDynamics", "openroboticsorg", "waymo",
    "Mobileye", "nvidia", "AMD", "intel", "tesla", "elonmusk",

    # Startups / VC / Industry
    "naval", "paulg", "pmarca", "reidhoffman", "balajis",
    "garrytan", "patrickc", "dharmesh", "sriramk",

    # Ethics / Policy
    "timnitGebru", "emilymbender", "ainowinstitute",
    "datasociety", "algorithmwatch", "mozilla",

    # Media / Curation
    "twimlai", "DeepLearningAI",
]

HUBS = [
    "karpathy",
    "ylecun",
    "AndrewYNg",
    "OpenAI",
    "GoogleDeepMind",
    "lexfridman",
    "huggingface",
]

ORG_ACCOUNTS = [
    "OpenAI",
    "AnthropicAI",
    "GoogleDeepMind",
    "huggingface",
    "nvidia"
]

from typing import List
import random

def build_twitter_relationship_model(
    influencers: List[str],
) -> RelationshipModel:
    graph = RelationshipModel()

    # Everyone follows the main hubs
    for user in influencers:
        for hub in HUBS:
            if user != hub:
                graph.add(RelationType.FOLLOW, user, hub)

    for user in influencers:
        peers = random.sample(
            [u for u in influencers if u != user],
            k=min(3, len(influencers) - 1),
        )
        for peer in peers:
            graph.add(RelationType.FOLLOW, user, peer)

    # Mentions (orgs / labs)
    for user in influencers:
        mentions = random.sample(
            ORG_ACCOUNTS,
            k=random.randint(1, 3),
        )
        for target in mentions:
            if user != target:
                graph.add(RelationType.MENTION, user, target)

    return graph

