# Sequence-Level Knowledge Distillation

## Method

This project uses sequence-level knowledge distillation to train
EleutherAI/pythia-70m for command intent and slot extraction.

The teacher model, Phi-3.5, generates JSON labels for English commands.
The generated command-and-JSON pairs are used as training examples.
The student receives the command as input and learns to generate the
corresponding JSON response.

Training uses the first 1,500 records from the cleaned training dataset.
The loss is calculated on the target JSON tokens, while the input command
tokens are excluded from the loss. The student is fine-tuned using
PyTorch and Hugging Face Transformers on CPU.

## Sequence-Level vs. Logit-Based Distillation

Sequence-level distillation uses the teacher's generated output as the
target sequence. The student learns to reproduce that output using
ordinary language-model training loss.

Logit-based distillation instead transfers the teacher's token
probability distribution (logits) to the student, usually through a
distribution-matching loss such as KL divergence. This provides
information about alternative token choices, not just the final
generated answer.

## Why Logit-Based Distillation Was Not Used

The teacher was accessed through the Ollama generation API. The
workflow used its generated JSON responses as labels and did not obtain
the teacher's token-level logits. Therefore, sequence-level distillation
was used. Additionally, the teacher and student are different model
families, making direct token-distribution matching less straightforward.

## Evaluation

All models were evaluated on the same 100 validation examples.

| Metric | Teacher | Original Pythia-70M | Fine-tuned Student |
|---|---:|---:|---:|
| JSON validity | 94% | 0% | 90% |
| Intent accuracy | 85% | 0% | 75% |
| Date accuracy | 71% | 0% | 68% |
| Time accuracy | 79% | 0% | 76% |
| Place accuracy | 81% | 0% | 77% |
| Full-frame accuracy | 44% | 0% | 41% |

The fine-tuned student substantially improved over the original
pretrained baseline. Its full-frame accuracy was 41%, compared with
44% for the teacher. Its JSON validity was 90%, compared with 94%
for the teacher.

## Limitation

The student was trained on only 1,500 teacher-labelled examples using
a relatively small 70-million-parameter model. Errors or inconsistencies
in teacher-generated labels can be learned by the student. The model
may also struggle with commands or slot expressions that are poorly
represented in the training data.
