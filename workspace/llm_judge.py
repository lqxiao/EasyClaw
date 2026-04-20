"""
LLM-as-a-Judge: Pairwise Response Comparison with Position Bias Mitigation

This module implements a robust pairwise judging system that:
1. Runs comparison in both orderings (A-first, B-first) to detect position bias
2. Extracts structured verdicts via constrained generation
3. Computes confidence from token probabilities
4. Aggregates results across both orderings for a final verdict
"""

import torch
import json
import re
from typing import Optional


# ============================================================
# 1. PROMPT TEMPLATE
# ============================================================

JUDGE_PROMPT_TEMPLATE = """You are an impartial judge evaluating two AI responses to a user prompt.

## User Prompt
{prompt}

## Response A
{response_a}

## Response B
{response_b}

## Evaluation Criteria
Evaluate based on: {criteria}

## Instructions
1. Analyze both responses against the criteria.
2. Provide your reasoning step by step.
3. Conclude with your verdict.

## Output Format (you MUST follow this exactly)
### Reasoning
<your step-by-step analysis here>

### Verdict
[[A]] if Response A is better
[[B]] if Response B is better
[[tie]] if they are roughly equal"""


# ============================================================
# 2. SINGLE-PASS JUDGING (one ordering)
# ============================================================

def _run_single_judgment(
    prompt: str,
    response_a: str,
    response_b: str,
    judge_model,
    judge_tokenizer,
    criteria: str,
    max_new_tokens: int = 1024,
) -> dict:
    """
    Run a single judgment pass. Returns raw verdict, reasoning, and
    token-level confidence for the verdict token.
    """
    # --- Build the prompt ---
    judge_input = JUDGE_PROMPT_TEMPLATE.format(
        prompt=prompt,
        response_a=response_a,
        response_b=response_b,
        criteria=criteria,
    )

    # --- Tokenize ---
    messages = [{"role": "user", "content": judge_input}]

    # Try chat template first (works for instruction-tuned models)
    if hasattr(judge_tokenizer, "apply_chat_template"):
        input_text = judge_tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        input_text = judge_input

    inputs = judge_tokenizer(input_text, return_tensors="pt").to(judge_model.device)

    # --- Generate with logprobs ---
    with torch.no_grad():
        outputs = judge_model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,           # Greedy for reproducibility
            temperature=1.0,           # Needed for meaningful logprobs
            return_dict_in_generate=True,
            output_scores=True,        # Get logits at each step
        )

    # --- Decode full response ---
    generated_ids = outputs.sequences[0][inputs["input_ids"].shape[1]:]
    full_response = judge_tokenizer.decode(generated_ids, skip_special_tokens=True)

    # --- Extract verdict ---
    verdict, confidence = _extract_verdict_and_confidence(
        full_response, generated_ids, outputs.scores, judge_tokenizer
    )

    # --- Extract reasoning ---
    reasoning = _extract_reasoning(full_response)

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reasoning": reasoning,
        "raw_output": full_response,
    }


# ============================================================
# 3. VERDICT & CONFIDENCE EXTRACTION
# ============================================================

def _extract_verdict_and_confidence(
    full_response: str,
    generated_ids: torch.Tensor,
    scores: tuple,
    tokenizer,
) -> tuple:
    """
    Extract the verdict ([[A]], [[B]], [[tie]]) and compute confidence
    from token probabilities.
    """
    # --- Regex extraction of verdict ---
    verdict_match = re.search(r"\[\[(A|B|tie)\]\]", full_response)

    if not verdict_match:
        # Fallback: look for less structured patterns
        lower = full_response.lower()
        if "response a is better" in lower or "response a wins" in lower:
            verdict = "A"
        elif "response b is better" in lower or "response b wins" in lower:
            verdict = "B"
        elif "tie" in lower or "equal" in lower or "neither" in lower:
            verdict = "tie"
        else:
            return "tie", 0.0  # Can't determine → low confidence tie

        return verdict, 0.5  # Fallback extraction → medium confidence

    verdict = verdict_match.group(1)

    # --- Compute confidence from logprobs ---
    # Find the token position where the verdict token was generated
    confidence = _compute_verdict_confidence(
        verdict, generated_ids, scores, tokenizer, full_response, verdict_match
    )

    return verdict, confidence


def _compute_verdict_confidence(
    verdict: str,
    generated_ids: torch.Tensor,
    scores: tuple,
    tokenizer,
    full_response: str,
    verdict_match: re.Match,
) -> float:
    """
    Compute confidence by looking at the probability distribution over
    verdict tokens (A, B, tie) at the position where the verdict was emitted.
    """
    if scores is None or len(scores) == 0:
        return 0.5  # No logprobs available

    try:
        # Find the character position of the verdict in the decoded text
        verdict_char_pos = verdict_match.start(1)

        # Approximate the token position by decoding incrementally
        # (character position → token position mapping)
        token_pos = _char_to_token_position(
            generated_ids, tokenizer, verdict_char_pos
        )

        if token_pos is None or token_pos >= len(scores):
            return 0.5

        # Get logits at the verdict position
        logits = scores[token_pos]  # Shape: (1, vocab_size)

        # Get token IDs for our verdict candidates
        candidate_tokens = {}
        for candidate in ["A", "B", "tie"]:
            token_ids = tokenizer.encode(candidate, add_special_tokens=False)
            if token_ids:
                candidate_tokens[candidate] = token_ids[0]

        if not candidate_tokens:
            return 0.5

        # Extract logits for candidates and compute softmax
        candidate_logits = torch.tensor([
            logits[0, candidate_tokens[c]].item()
            for c in candidate_tokens
        ])
        probs = torch.softmax(candidate_logits, dim=0)

        # Confidence = probability of the chosen verdict among {A, B, tie}
        candidate_list = list(candidate_tokens.keys())
        verdict_idx = candidate_list.index(verdict) if verdict in candidate_list else 0
        confidence = probs[verdict_idx].item()

        return round(confidence, 4)

    except Exception:
        return 0.5  # Fallback


def _char_to_token_position(
    generated_ids: torch.Tensor,
    tokenizer,
    target_char_pos: int,
) -> Optional[int]:
    """Map a character position in the decoded string to a token index."""
    char_count = 0
    for i, token_id in enumerate(generated_ids):
        token_str = tokenizer.decode([token_id.item()], skip_special_tokens=True)
        char_count += len(token_str)
        if char_count > target_char_pos:
            return i
    return None


def _extract_reasoning(full_response: str) -> str:
    """Extract the reasoning section from the judge's output."""
    # Try to extract between ### Reasoning and ### Verdict
    match = re.search(
        r"###\s*Reasoning\s*\n(.*?)###\s*Verdict",
        full_response,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    # Fallback: everything before the verdict marker
    match = re.search(r"(.*?)\[\[(?:A|B|tie)\]\]", full_response, re.DOTALL)
    if match:
        return match.group(1).strip()

    return full_response.strip()


# ============================================================
# 4. MAIN FUNCTION: POSITION-BIAS-AWARE JUDGING
# ============================================================

def judge_pairwise(
    prompt: str,
    response_a: str,
    response_b: str,
    judge_model,
    judge_tokenizer,
    criteria: str = "helpfulness, accuracy, and clarity",
) -> dict:
    """
    Use the LLM to judge which response is better.

    ⚠️ Handles POSITION BIAS by running the comparison twice:
       Pass 1: A shown first, B shown second
       Pass 2: B shown first, A shown second (then remap verdict)

    Returns:
        {
            "winner": "A" | "B" | "tie",
            "confidence": float,       # 0-1, aggregated confidence
            "reasoning": str,          # reasoning from the primary pass
            "position_bias_detected": bool,
            "details": {
                "pass1": { ... },      # A-first results
                "pass2": { ... },      # B-first results (remapped)
            }
        }
    """
    # ---- Pass 1: Original order (A first, B second) ----
    pass1 = _run_single_judgment(
        prompt=prompt,
        response_a=response_a,
        response_b=response_b,
        judge_model=judge_model,
        judge_tokenizer=judge_tokenizer,
        criteria=criteria,
    )

    # ---- Pass 2: Swapped order (B first, A second) ----
    pass2_raw = _run_single_judgment(
        prompt=prompt,
        response_a=response_b,   # ← SWAPPED
        response_b=response_a,   # ← SWAPPED
        judge_model=judge_model,
        judge_tokenizer=judge_tokenizer,
        criteria=criteria,
    )

    # Remap Pass 2 verdict back to original labels
    # (If swapped judge says "A wins", it means original B wins)
    REMAP = {"A": "B", "B": "A", "tie": "tie"}
    pass2 = {
        "verdict": REMAP[pass2_raw["verdict"]],
        "confidence": pass2_raw["confidence"],
        "reasoning": pass2_raw["reasoning"],
        "raw_output": pass2_raw["raw_output"],
    }

    # ---- Aggregate Results ----
    result = _aggregate_verdicts(pass1, pass2)

    return result


# ============================================================
# 5. AGGREGATION LOGIC
# ============================================================

def _aggregate_verdicts(pass1: dict, pass2: dict) -> dict:
    """
    Aggregate two passes into a final verdict.

    Agreement Matrix:
    ┌──────────┬──────────┬──────────────────────────────────┐
    │  Pass 1  │  Pass 2  │  Result                          │
    ├──────────┼──────────┼──────────────────────────────────┤
    │  A       │  A       │  A wins (high confidence)        │
    │  B       │  B       │  B wins (high confidence)        │
    │  A       │  B       │  Tie (position bias detected)    │
    │  B       │  A       │  Tie (position bias detected)    │
    │  A       │  tie     │  A wins (lower confidence)       │
    │  tie     │  A       │  A wins (lower confidence)       │
    │  B       │  tie     │  B wins (lower confidence)       │
    │  tie     │  B       │  B wins (lower confidence)       │
    │  tie     │  tie     │  Tie (high confidence)           │
    └──────────┴──────────┴──────────────────────────────────┘
    """
    v1 = pass1["verdict"]
    v2 = pass2["verdict"]
    c1 = pass1["confidence"]
    c2 = pass2["confidence"]

    position_bias_detected = False

    if v1 == v2:
        # ✅ Both passes agree → strong signal
        winner = v1
        confidence = (c1 + c2) / 2  # Average confidence
        reasoning = pass1["reasoning"]  # Use Pass 1 reasoning as primary

    elif {v1, v2} == {"A", "B"}:
        # ❌ Direct contradiction → position bias detected
        position_bias_detected = True

        # Check if one pass was much more confident
        if abs(c1 - c2) > 0.3:
            # Go with the more confident pass
            winner = v1 if c1 > c2 else v2
            confidence = max(c1, c2) * 0.5  # Penalize confidence heavily
            reasoning = pass1["reasoning"] if c1 > c2 else pass2["reasoning"]
        else:
            # Similar confidence → can't determine → tie
            winner = "tie"
            confidence = 1.0 - (c1 + c2) / 2  # Low confidence
            reasoning = (
                f"Position bias detected. "
                f"Pass 1 (A-first) chose {v1} (conf={c1:.2f}). "
                f"Pass 2 (B-first) chose {v2} (conf={c2:.2f}). "
                f"Defaulting to tie."
            )

    else:
        # One says A/B, the other says tie → lean toward the non-tie verdict
        non_tie = v1 if v1 != "tie" else v2
        non_tie_conf = c1 if v1 != "tie" else c2
        winner = non_tie
        confidence = non_tie_conf * 0.75  # Slight confidence penalty
        reasoning = pass1["reasoning"]

    return {
        "winner": winner,
        "confidence": round(min(max(confidence, 0.0), 1.0), 4),
        "reasoning": reasoning,
        "position_bias_detected": position_bias_detected,
        "details": {
            "pass1_ab_order": {
                "verdict": pass1["verdict"],
                "confidence": pass1["confidence"],
                "reasoning": pass1["reasoning"],
            },
            "pass2_ba_order": {
                "verdict": pass2["verdict"],
                "confidence": pass2["confidence"],
                "reasoning": pass2["reasoning"],
            },
        },
    }


# ============================================================
# 6. BATCH EVALUATION RUNNER
# ============================================================

def judge_batch(
    test_cases: list[dict],
    judge_model,
    judge_tokenizer,
    criteria: str = "helpfulness, accuracy, and clarity",
) -> list[dict]:
    """Run pairwise judging on a batch of test cases."""
    results = []
    for i, case in enumerate(test_cases):
        print(f"\n{'='*60}")
        print(f"Judging case {i+1}/{len(test_cases)}: {case['prompt'][:60]}...")
        print(f"{'='*60}")

        result = judge_pairwise(
            prompt=case["prompt"],
            response_a=case["response_a"],
            response_b=case["response_b"],
            judge_model=judge_model,
            judge_tokenizer=judge_tokenizer,
            criteria=criteria,
        )

        result["prompt"] = case["prompt"]
        results.append(result)

        # Print summary
        bias_flag = " ⚠️ POSITION BIAS" if result["position_bias_detected"] else ""
        print(f"  Winner: {result['winner']} "
              f"(confidence: {result['confidence']:.2f}){bias_flag}")

    return results


# ============================================================
# 7. PRETTY PRINT RESULTS
# ============================================================

def print_results(results: list[dict]):
    """Pretty print judging results."""
    print("\n" + "=" * 70)
    print("JUDGING RESULTS SUMMARY")
    print("=" * 70)

    for i, r in enumerate(results):
        prompt_short = r["prompt"][:50] + "..." if len(r["prompt"]) > 50 else r["prompt"]
        bias = " ⚠️  BIAS" if r["position_bias_detected"] else ""

        print(f"\n{'─'*70}")
        print(f"Case {i+1}: {prompt_short}")
        print(f"{'─'*70}")
        print(f"  🏆 Winner:     {r['winner']}{bias}")
        print(f"  📊 Confidence: {r['confidence']:.2f}")
        print(f"  📝 Reasoning:  {r['reasoning'][:200]}...")
        print(f"  ├─ Pass 1 (A-first): {r['details']['pass1_ab_order']['verdict']} "
              f"(conf={r['details']['pass1_ab_order']['confidence']:.2f})")
        print(f"  └─ Pass 2 (B-first): {r['details']['pass2_ba_order']['verdict']} "
              f"(conf={r['details']['pass2_ba_order']['confidence']:.2f})")

    # Overall stats
    winners = [r["winner"] for r in results]
    print(f"\n{'='*70}")
    print(f"TOTALS: A wins: {winners.count('A')} | "
          f"B wins: {winners.count('B')} | "
          f"Ties: {winners.count('tie')}")
    bias_count = sum(1 for r in results if r["position_bias_detected"])
    print(f"Position bias detected in {bias_count}/{len(results)} cases")
    print(f"{'='*70}")


# ============================================================
# 8. EXAMPLE USAGE
# ============================================================

if __name__ == "__main__":
    # --- Example with mock model (for testing the logic) ---
    # In production, replace with:
    #   from transformers import AutoModelForCausalLM, AutoTokenizer
    #   model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3-8B-Instruct")
    #   tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3-8B-Instruct")

    test_cases = [
        {
            "prompt": "Explain photosynthesis to a 5-year-old.",
            "response_a": "Plants eat sunlight! They use their green leaves like tiny solar panels to catch light from the sun. Then they mix it with water from the ground and air to make their own food. It's like cooking, but for plants!",
            "response_b": "Photosynthesis is the process by which plants convert light energy, usually from the sun, into chemical energy that can be later released to fuel the plant's activities. This process involves the absorption of carbon dioxide and water.",
        },
        {
            "prompt": "Write a haiku about programming.",
            "response_a": "Semicolons lost\nThe compiler screams again\nDebug until dawn",
            "response_b": "Code flows like water\nBugs hide in the logic deep\nStack overflow helps",
        },
        {
            "prompt": "What are three benefits of exercise?",
            "response_a": "Exercise improves cardiovascular health, boosts mental well-being by releasing endorphins, and helps maintain a healthy weight through calorie expenditure.",
            "response_b": "1. Makes you stronger and healthier heart\n2. Makes you feel happier because of brain chemicals\n3. Helps you not gain too much weight\n4. Also helps you sleep better\n5. Good for your bones too",
        },
    ]

    print("To run with a real model:")
    print("  from transformers import AutoModelForCausalLM, AutoTokenizer")
    print("  model = AutoModelForCausalLM.from_pretrained('your-model')")
    print("  tokenizer = AutoTokenizer.from_pretrained('your-model')")
    print("  results = judge_batch(test_cases, model, tokenizer)")
    print("  print_results(results)")
