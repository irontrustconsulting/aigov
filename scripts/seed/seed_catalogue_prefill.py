"""
Curation seed: hosting_model_id and intended_use for catalogue_product.

Populates typed prefill knowledge (D-69) for the design-partner cohort and the
broader active catalogue. Uncurated products remain NULL — the intake wizard
degrades gracefully (blank select, no purpose prefill).

Idempotent: re-running converges to the described state; does not create or
delete products.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CatalogueProduct
from app.models.intake import HostingModel
from scripts.seed.common import make_engine


# product name → (hosting_model_code, intended_use)
CURATION: dict[str, tuple[str, str]] = {
    # ── Design-partner cohort (cloud SaaS) ──────────────────────────────────
    "ChatGPT Enterprise": (
        "cloud_saas",
        "AI assistant for employee productivity, writing, coding, and analysis",
    ),
    "Claude API": (
        "cloud_saas",
        "AI language model for enterprise natural language and reasoning tasks",
    ),
    "Azure OpenAI Service": (
        "cloud_saas",
        "Managed OpenAI models for enterprise AI integration via Microsoft Azure",
    ),
    "Amazon Bedrock": (
        "cloud_saas",
        "Managed foundation model access and generative AI application development",
    ),
    "Microsoft 365 Copilot": (
        "cloud_saas",
        "AI-powered productivity assistant embedded in Microsoft 365 applications",
    ),
    "Copilot Studio": (
        "cloud_saas",
        "Low-code AI copilot and chatbot builder for enterprise workflows",
    ),
    "Agentforce (Einstein AI)": (
        "cloud_saas",
        "AI agents for CRM automation, customer service, and sales engagement",
    ),
    "GitHub Copilot": (
        "cloud_saas",
        "AI pair programmer for code completion, review, and generation",
    ),
    "Gemini for Google Workspace": (
        "cloud_saas",
        "AI assistant embedded in Google Workspace for productivity and collaboration",
    ),
    "Vertex AI (Gemini API)": (
        "cloud_saas",
        "Managed foundation model access and AI development platform on Google Cloud",
    ),
    # ── Extended catalogue ───────────────────────────────────────────────────
    "Amazon Q Business": (
        "cloud_saas",
        "Enterprise AI assistant for knowledge retrieval and business automation",
    ),
    "Atlassian Intelligence": (
        "cloud_saas",
        "AI features across Atlassian products for development and project workflows",
    ),
    "Box AI": (
        "cloud_saas",
        "AI-powered document analysis and content intelligence within Box",
    ),
    "Grammarly Business": (
        "cloud_saas",
        "AI writing assistant for clarity, correctness, and tone in business communication",
    ),
    "Notion AI": (
        "cloud_saas",
        "AI writing and knowledge management features within Notion",
    ),
    "HubSpot Breeze AI": (
        "cloud_saas",
        "AI-assisted CRM features for marketing, sales, and customer service automation",
    ),
    "Intercom Fin AI Agent": (
        "cloud_saas",
        "AI customer service agent for automated support resolution",
    ),
    "Glean Work AI": (
        "cloud_saas",
        "Enterprise AI search and knowledge assistant across connected data sources",
    ),
    "Gong Revenue Intelligence": (
        "cloud_saas",
        "AI-driven analysis of sales conversations for revenue optimisation",
    ),
    "ServiceNow Now Intelligence": (
        "cloud_saas",
        "AI-driven workflow automation and virtual agent for enterprise IT and HR",
    ),
    "Moveworks AI Platform": (
        "cloud_saas",
        "AI employee support platform for IT, HR, and enterprise service automation",
    ),
    "IBM watsonx.ai": (
        "cloud_saas",
        "AI development studio for training, tuning, and deploying foundation models",
    ),
    "IBM watsonx Assistant": (
        "cloud_saas",
        "AI virtual assistant for customer and employee self-service automation",
    ),
    "OpenAI API": (
        "cloud_saas",
        "Foundation model API for building custom generative AI features and applications",
    ),
    "Mistral API (le Chat Enterprise)": (
        "cloud_saas",
        "Open-weight foundation model API for enterprise language tasks",
    ),
    "Cohere Platform (Command R+)": (
        "cloud_saas",
        "Retrieval-augmented generation and enterprise language model platform",
    ),
    "Databricks Assistant & DBRX": (
        "cloud_saas",
        "AI assistant and foundation model for data engineering and analytics workflows",
    ),
    "SAP Joule": (
        "cloud_saas",
        "AI copilot embedded in SAP applications for business process automation",
    ),
    "Oracle AI Services": (
        "cloud_saas",
        "AI services for language, vision, and anomaly detection in Oracle Cloud",
    ),
    "Freddy AI": (
        "cloud_saas",
        "AI agent for customer support, IT service management, and CRM automation",
    ),
    "Tableau Pulse": (
        "cloud_saas",
        "AI-powered data insights and analytics digest for business intelligence",
    ),
    "Leena AI (WorkLM)": (
        "cloud_saas",
        "AI HR and employee experience platform for self-service and automation",
    ),
    "Eightfold Talent Intelligence": (
        "cloud_saas",
        "AI talent platform for recruitment, retention, and workforce intelligence",
    ),
    "Harvey (Legal AI)": (
        "cloud_saas",
        "AI platform for legal research, contract analysis, and drafting",
    ),
    "Lexis+ AI": (
        "cloud_saas",
        "AI legal research and document analysis for law firms and legal teams",
    ),
    "DeepL Pro": (
        "cloud_saas",
        "AI-powered translation service for enterprise document and communication workflows",
    ),
    "Perplexity Enterprise Pro": (
        "cloud_saas",
        "AI-powered search and knowledge retrieval for enterprise research workflows",
    ),
    "Jasper AI": (
        "cloud_saas",
        "AI marketing content creation platform for copywriting and brand materials",
    ),
    "Copy.ai": (
        "cloud_saas",
        "AI go-to-market platform for marketing copy and sales workflow automation",
    ),
    "Grammarly Business": (
        "cloud_saas",
        "AI writing assistant for clarity, correctness, and tone in business communication",
    ),
    "Fireflies Business": (
        "cloud_saas",
        "AI meeting assistant for transcription, summarisation, and action item capture",
    ),
    "Otter Business": (
        "cloud_saas",
        "AI meeting transcription and note-taking for real-time collaboration",
    ),
    "ElevenLabs Business": (
        "cloud_saas",
        "AI voice synthesis platform for audio content and voice application development",
    ),
    "Runway Gen-3 (Enterprise)": (
        "cloud_saas",
        "AI video and image generation for creative and media production workflows",
    ),
    "Midjourney": (
        "cloud_saas",
        "AI image generation for creative, design, and marketing content production",
    ),
    "Palantir AIP (AI Platform)": (
        "cloud_saas",
        "AI-enabled decision platform for operational intelligence and workflow orchestration",
    ),
    "Darktrace AI Platform": (
        "cloud_saas",
        "AI cybersecurity platform for autonomous threat detection and response",
    ),
    "Charlotte AI (Falcon Platform)": (
        "cloud_saas",
        "AI-powered cybersecurity assistant for threat investigation and response",
    ),
    "Scale Data Engine (Enterprise)": (
        "cloud_saas",
        "AI data labelling and evaluation platform for model training and assessment",
    ),
    "HireVue Video Interviewing": (
        "cloud_saas",
        "AI-assisted video interviewing and candidate assessment for talent acquisition",
    ),
    "Olivia (Paradox AI)": (
        "cloud_saas",
        "AI conversational recruiting assistant for candidate screening and scheduling",
    ),
    "Phenom Talent AI": (
        "cloud_saas",
        "AI talent experience platform for candidate engagement and workforce intelligence",
    ),
    "Checkr AI Background Screening": (
        "cloud_saas",
        "AI-assisted background screening and employment verification platform",
    ),
    "Guru AI Knowledge": (
        "cloud_saas",
        "AI knowledge management and search for internal team documentation",
    ),
    "Outreach Sales Execution AI": (
        "cloud_saas",
        "AI sales execution platform for pipeline management and rep coaching",
    ),
    "Pendo AI": (
        "cloud_saas",
        "AI-powered product analytics and in-app guidance for user experience teams",
    ),
    "RelativityOne AI": (
        "cloud_saas",
        "AI-assisted e-discovery and legal review platform for litigation and compliance",
    ),
    "ThoughtSpot AI Analytics": (
        "cloud_saas",
        "AI-powered search analytics and business intelligence for self-service data",
    ),
    "Textio": (
        "cloud_saas",
        "AI writing guidance platform for inclusive and effective job descriptions and feedback",
    ),
    "Snowflake Cortex AI": (
        "cloud_saas",
        "AI services and LLM functions embedded within the Snowflake data cloud",
    ),
    "UiPath Autopilot": (
        "cloud_saas",
        "AI-powered automation platform for robotic process automation and agent workflows",
    ),
    "Adobe Acrobat AI Assistant": (
        "cloud_saas",
        "AI document assistant for summarisation, Q&A, and content extraction in PDFs",
    ),
    "Firefly": (
        "cloud_saas",
        "AI creative image and content generation tool for design and marketing workflows",
    ),
    "ABBYY Vantage": (
        "cloud_saas",
        "AI-powered intelligent document processing and data extraction platform",
    ),
}


def main(session: Session | None = None) -> None:
    own = session is None
    if own:
        session = Session(make_engine())

    try:
        # Build hosting_model code → id lookup
        hm_rows = session.scalars(select(HostingModel)).all()
        hm_by_code: dict[str, str] = {hm.code: str(hm.id) for hm in hm_rows}

        products = session.scalars(select(CatalogueProduct)).all()
        product_by_name: dict[str, CatalogueProduct] = {p.name: p for p in products}

        updated = skipped = missing = 0
        for product_name, (hm_code, intended_use) in CURATION.items():
            product = product_by_name.get(product_name)
            if product is None:
                missing += 1
                print(f"  ~ missing   {product_name!r} (not in catalogue)")
                continue

            hm_id = hm_by_code.get(hm_code)
            if hm_id is None:
                skipped += 1
                print(f"  ~ no hm     {product_name!r}: hosting_model code {hm_code!r} not found")
                continue

            import uuid as _uuid
            product.hosting_model_id = _uuid.UUID(hm_id)
            product.intended_use = intended_use
            updated += 1

        if own:
            session.commit()

        print(
            f"  catalogue prefill: {updated} curated, "
            f"{skipped} skipped, {missing} not found in catalogue"
        )
    finally:
        if own:
            session.close()


if __name__ == "__main__":
    main()
