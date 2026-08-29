from __future__ import annotations

import uuid
from typing import Any

from ..models import (
    CandidateInterventionEvaluation,
    CustomerRevenueContext,
    FailureCategory,
    GuardrailStatus,
    InterventionDecision,
    InterventionType,
    LeakageType,
    RecoveryPrediction,
    RevenueEvent,
    RootCauseAnalysis,
)


class RevenueRecoveryDecisionAgent:
    """Intervention Optimization Agent evaluating & selecting optimal bounded intervention."""

    CANDIDATE_COSTS = {
        InterventionType.RETRY: 1.0,
        InterventionType.DELAYED_RETRY: 2.0,
        InterventionType.UPDATE_PAYMENT_METHOD: 15.0,
        InterventionType.PAYMENT_REMINDER: 5.0,
        InterventionType.PERSONALIZED_MESSAGE: 8.0,
        InterventionType.CHECKOUT_RECOVERY: 10.0,
        InterventionType.INVOICE_REMINDER: 5.0,
        InterventionType.HUMAN_ESCALATION: 50.0,
        InterventionType.NO_ACTION: 0.0,
    }

    CANDIDATE_FRICTION = {
        InterventionType.RETRY: 10.0,
        InterventionType.DELAYED_RETRY: 2.0,
        InterventionType.UPDATE_PAYMENT_METHOD: 5.0,
        InterventionType.PAYMENT_REMINDER: 3.0,
        InterventionType.PERSONALIZED_MESSAGE: 4.0,
        InterventionType.CHECKOUT_RECOVERY: 3.0,
        InterventionType.INVOICE_REMINDER: 2.0,
        InterventionType.HUMAN_ESCALATION: 0.0,
        InterventionType.NO_ACTION: 0.0,
    }

    def decide_intervention(
        self,
        event: RevenueEvent,
        context: CustomerRevenueContext,
        root_cause: RootCauseAnalysis,
        prediction: RecoveryPrediction,
    ) -> InterventionDecision:
        decision_id = f"dec_{uuid.uuid4().hex[:10]}"
        amount = event.amount
        base_prob = prediction.recovery_probability
        category = root_cause.category

        # Hard Security Override
        if category == FailureCategory.SECURITY_OR_FRAUD:
            return InterventionDecision(
                decision_id=decision_id,
                recommended_action=InterventionType.HUMAN_ESCALATION,
                reasoning="Security/fraud flag detected. Automatic retries prohibited for merchant safety.",
                expected_net_recovery=0.0,
                estimated_cost=50.0,
                requires_human=True,
                candidate_evaluations=[
                    CandidateInterventionEvaluation(
                        action_type=InterventionType.HUMAN_ESCALATION,
                        predicted_probability=0.05,
                        expected_recovery_value=0.0,
                        estimated_cost=50.0,
                        friction_penalty=0.0,
                        net_expected_value=-50.0,
                        recommended=True,
                        status=GuardrailStatus.HUMAN_REVIEW,
                    )
                ],
            )

        # Evaluate candidate interventions across all 9 possible action types
        candidate_evaluations: list[CandidateInterventionEvaluation] = []
        all_candidate_types = list(InterventionType)

        for candidate_action in all_candidate_types:
            cand_prob = self._evaluate_candidate_probability(
                candidate_action, base_prob, category, event.leakage_type, context
            )
            cost = self.CANDIDATE_COSTS.get(candidate_action, 5.0)
            friction = self.CANDIDATE_FRICTION.get(candidate_action, 5.0)

            # Extra friction penalty if customer has already received multiple past interventions
            if context.previous_interventions_count >= 2 and candidate_action not in (
                InterventionType.NO_ACTION,
                InterventionType.HUMAN_ESCALATION,
            ):
                friction += 15.0

            exp_val = round(amount * cand_prob, 2)
            net_val = round(exp_val - cost - friction, 2)

            status = GuardrailStatus.APPROVED
            rejection_reason = None

            # Candidate suitability checks
            if candidate_action in (InterventionType.RETRY, InterventionType.DELAYED_RETRY):
                if category in (
                    FailureCategory.SECURITY_OR_FRAUD,
                    FailureCategory.INVALID_PAYMENT_METHOD,
                    FailureCategory.HARD_DECLINE,
                ):
                    status = GuardrailStatus.REJECTED
                    rejection_reason = f"Action unsuitable for category '{category.value}'"
            elif candidate_action == InterventionType.CHECKOUT_RECOVERY and event.leakage_type != LeakageType.CHECKOUT_ABANDONMENT:
                status = GuardrailStatus.REJECTED
                rejection_reason = "Checkout recovery applicable to checkout abandonment only"
            elif candidate_action == InterventionType.INVOICE_REMINDER and event.leakage_type != LeakageType.OVERDUE_RECEIVABLE:
                status = GuardrailStatus.REJECTED
                rejection_reason = "Invoice reminder applicable to overdue receivables only"

            eval_item = CandidateInterventionEvaluation(
                action_type=candidate_action,
                predicted_probability=round(cand_prob, 3),
                expected_recovery_value=exp_val,
                estimated_cost=cost,
                friction_penalty=friction,
                net_expected_value=net_val,
                recommended=False,
                status=status,
                rejection_reason=rejection_reason,
            )
            candidate_evaluations.append(eval_item)

        # Select best approved candidate action maximizing Net Expected Value
        approved_candidates = [
            c for c in candidate_evaluations if c.status != GuardrailStatus.REJECTED
        ]

        if approved_candidates:
            winning_candidate = max(approved_candidates, key=lambda c: c.net_expected_value)
        else:
            winning_candidate = candidate_evaluations[-1]  # NO_ACTION

        # Mark winning candidate
        for c in candidate_evaluations:
            if c.action_type == winning_candidate.action_type:
                c.recommended = True

        best_action = winning_candidate.action_type
        delay_hours = 0
        if best_action == InterventionType.DELAYED_RETRY:
            delay_hours = 48 if category == FailureCategory.INSUFFICIENT_FUNDS else 24

        requires_human = (
            best_action == InterventionType.HUMAN_ESCALATION
            or amount >= 50000.0
            or winning_candidate.status == GuardrailStatus.HUMAN_REVIEW
        )

        reasoning = (
            f"Intervention '{best_action.value}' won candidate optimization with highest net value ₹{winning_candidate.net_expected_value:,.2f} "
            f"(P_recovery = {int(winning_candidate.predicted_probability * 100)}%, Expected Recovery = ₹{winning_candidate.expected_recovery_value:,.2f})."
        )

        personalized_copy = None
        if best_action == InterventionType.CHECKOUT_RECOVERY:
            personalized_copy = f"Hi {context.name}, complete your ₹{amount:,.2f} purchase with 1 click: https://rzp.io/i/recov_{event.event_id[:6]}"
        elif best_action == InterventionType.INVOICE_REMINDER:
            personalized_copy = f"Invoice payment of ₹{amount:,.2f} is past due. Pay securely via Razorpay: https://rzp.io/i/inv_{event.event_id[:6]}"
        elif best_action == InterventionType.UPDATE_PAYMENT_METHOD:
            personalized_copy = f"Hi {context.name}, please update your card/UPI for your ₹{amount:,.2f} subscription: https://rzp.io/i/update_{context.customer_id[:6]}"

        return InterventionDecision(
            decision_id=decision_id,
            recommended_action=best_action,
            reasoning=reasoning,
            expected_net_recovery=winning_candidate.net_expected_value,
            estimated_cost=winning_candidate.estimated_cost,
            timing_delay_hours=delay_hours,
            personalized_copy=personalized_copy,
            requires_human=requires_human,
            candidate_evaluations=candidate_evaluations,
        )

    def _evaluate_candidate_probability(
        self,
        action: InterventionType,
        base_prob: float,
        category: FailureCategory,
        leakage_type: LeakageType,
        context: CustomerRevenueContext,
    ) -> float:
        if action == InterventionType.NO_ACTION:
            return 0.05 if category != FailureCategory.TEMPORARY_PROCESSING else 0.20

        if action == InterventionType.HUMAN_ESCALATION:
            return 0.50 if context.ltv > 20000 else 0.30

        if category == FailureCategory.INSUFFICIENT_FUNDS:
            if action == InterventionType.DELAYED_RETRY:
                return min(0.85, base_prob + 0.22)  # Delay allows account reloading
            if action == InterventionType.RETRY:
                return max(0.20, base_prob - 0.20)  # Immediate retry fails on insufficient funds
            if action in (InterventionType.PAYMENT_REMINDER, InterventionType.PERSONALIZED_MESSAGE):
                return min(0.75, base_prob + 0.10)

        if category == FailureCategory.TEMPORARY_PROCESSING:
            if action == InterventionType.RETRY:
                return min(0.95, base_prob + 0.15)
            if action == InterventionType.DELAYED_RETRY:
                return min(0.85, base_prob)

        if category == FailureCategory.INVALID_PAYMENT_METHOD:
            if action == InterventionType.UPDATE_PAYMENT_METHOD:
                return min(0.70, base_prob + 0.35)
            return 0.10

        if leakage_type == LeakageType.CHECKOUT_ABANDONMENT:
            if action == InterventionType.CHECKOUT_RECOVERY:
                return min(0.88, base_prob + 0.30)
            return 0.15

        if leakage_type == LeakageType.OVERDUE_RECEIVABLE:
            if action == InterventionType.INVOICE_REMINDER:
                return min(0.82, base_prob + 0.25)
            return 0.25

        return base_prob
