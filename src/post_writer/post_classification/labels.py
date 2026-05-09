BINARY_LABELS = [
    (
        "Technical content about AI, data, machine learning, NLP, or software engineering "
        "implementation details such as methods, architectures, algorithms, "
        "or code-level discussion"
    ),
    (
        "Non-technical content such as opinions, social or political commentary, "
        "industry news, announcements, founder stories, product launches, "
        "hiring posts, or high-level discussion of AI without technical details"
    )
]

LABEL_DEFINITIONS = {
    (
        "Technical content on generative AI and foundation models, including large language models (LLMs), "
        "agent-based systems, prompt engineering, pretraining and fine-tuning, "
        "evaluation methodologies, and comparative analysis of generative models."
    ): "Generative AI",
    (
        "Natural Language Processing (NLP), focusing on technical methods and systems for understanding, analyzing, "
        "and transforming human language text or speech. Includes tasks such as tokenization, parsing, "
        "named entity recognition, text classification, information extraction, embeddings, "
        "semantic similarity, and linguistic feature modeling. Excludes high-level commentary or opinions."
    ): "NLP",
    (
        "Machine Learning, focusing on technical content with details of general machine learning algorithms, theory, or training methods "
        "such as supervised, unsupervised, or reinforcement learning that are not specific "
        "to generative foundation models."
    ): "Machine Learning",
    (
        "MLOps and Orchestration, focusing on operational systems for machine learning, "
        "including training pipelines, deployment, monitoring, CI/CD, infrastructure, "
        "and reliability engineering. Excludes model research, scaling laws, or training science."
    ): "Orchestration",
    (
        "Data Analytics, focusing on data analysis, reporting, dashboards, statistics, "
        "and business intelligence rather than machine learning model development."
    ): "Data Analytics",
    (
        "Robotics, focusing on AI systems for robotic perception, control, motion planning, "
        "and automation in physical or autonomous robotic systems."
    ): "Robotics"
}
