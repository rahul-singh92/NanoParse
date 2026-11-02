# AI Usage Disclosure — NanoParse

## 1. AI tools used

### Ollama — Phi-3.5
Used as a teacher model to generate structured intent and slot annotations for the command dataset.

### EleutherAI Pythia-70M
Used as the student language model, fine-tuned on the cleaned command dataset to generate JSON predictions for NanoParse.

### ChatGPT
Used as a development assistant for technical explanations, debugging, reviewing implementation choices, and assistance with deployment and testing workflows. All commands and changes were reviewed and executed by the project developer.

## 2. Dataset preparation

Teacher-generated annotations were not accepted blindly. A cleaning pipeline checked:
- JSON validity and required keys.
- Intent values against the allowed schema.
- Slot values against the original command text.
- Duplicate commands.

Invalid or inconsistent records were discarded. The resulting v1 training dataset contains 2,292 examples.

## 3. Human oversight

The project developer made the final decisions about:
- Dataset cleaning and schema requirements.
- Model training configuration and model selection.
- API validation and deployment configuration.
- Evaluation, testing, and interpretation of results.

AI-generated suggestions and annotations were treated as assistance, not as authoritative results.

## 4. Evaluation and limitations

The production v1 model achieved 90% JSON validity on the validation set. Its full-frame accuracy was 41%.

Testing also showed that some commands produce malformed JSON or incorrect slot values. The API validates model output and returns an error rather than silently accepting invalid predictions.

The model is a small experimental model and should not be treated as a reliable general-purpose language understanding system.

## 5. Privacy and security

The project uses command examples for training and evaluation. No credentials, API keys, or private user information should be included in training data or prompts.

Secrets are supplied through Kubernetes configuration rather than hardcoded into application source code.

## 6. Final responsibility

The project developer is responsible for reviewing AI-assisted work, verifying test results, documenting limitations, and ensuring that the submitted implementation behaves as reported.
