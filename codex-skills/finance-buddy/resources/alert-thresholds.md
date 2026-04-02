# Finance Buddy - Alert Thresholds & Rules

This document defines all alert conditions, thresholds, and escalation rules used by the finance-buddy skill.

---

## Alert Priority Levels

### 🚨 CRITICAL
- **Response Time**: Immediate action required
- **Impact**: High financial risk or deadline pressure
- **Display**: Always shown prominently on dashboard
- **Notification**: Alert user on every skill invocation until resolved

### ⚠️ WARNING
- **Response Time**: Action needed within 1-7 days
- **Impact**: Approaching threshold or deadline
- **Display**: Shown on dashboard
- **Notification**: Alert user once daily until resolved

### 💡 OPPORTUNITY
- **Response Time**: No urgency, but beneficial to act
- **Impact**: Potential savings or optimization
- **Display**: Shown in opportunities section
- **Notification**: Mention when relevant to current context

### 📊 INSIGHT
- **Response Time**: Informational only
- **Impact**: Pattern recognition, trend observation
- **Display**: Shown in insights section
- **Notification**: Passive observation, no action required

---

## Burn Rate Alerts

### Critical Burn Rate Alert 🚨
```yaml
condition:
  burn_rate_7day > config.burn_rate.alert_threshold
  AND burn_rate_trend = "increasing"

threshold:
  default: 150  # $/day
  configurable: true

message: |
  🚨 CRITICAL: High burn rate detected!
  - Current: $[X]/day (7-day average)
  - Threshold: $[Y]/day
  - Trend: Increasing [Z]%
  - Action: Immediate spending reduction needed

trigger_frequency: "daily"
auto_resolve: burn_rate_7day < threshold
```

### Warning Burn Rate Alert ⚠️
```yaml
condition:
  burn_rate_7day > (config.burn_rate.alert_threshold * 0.80)
  OR burn_rate_increase > 0.20  # 20% increase

threshold:
  default: 120  # $/day (80% of critical)
  increase_threshold: 0.20  # 20% increase

message: |
  ⚠️ WARNING: Burn rate increasing
  - Current: $[X]/day
  - Previous: $[Y]/day
  - Increase: [Z]%
  - Recommendation: Review spending patterns

trigger_frequency: "weekly"
auto_resolve: burn_rate_7day < threshold AND burn_rate_stable
```

### Burn Rate Insight 📊
```yaml
condition:
  burn_rate_decreased > 0.15  # 15% decrease
  OR new_low_burn_rate_achieved

message: |
  📊 INSIGHT: Burn rate improvement!
  - Current: $[X]/day
  - Previous: $[Y]/day
  - Improvement: [Z]%
  - Great work! Keep it up.

trigger_frequency: "on_improvement"
```

---

## Runway Alerts

### Critical Runway Alert 🚨
```yaml
condition:
  runway_days < config.burn_rate.runway_critical
  OR runway_depletion_date < 30_days_from_now

threshold:
  default: 30  # days
  configurable: true

message: |
  🚨 CRITICAL: Emergency fund critically low!
  - Runway: [X] days
  - Depletion Date: [Date]
  - Emergency Fund: $[Y]
  - Action: Immediate income increase or drastic spending cuts needed

trigger_frequency: "daily"
escalation: "increase to hourly if runway < 7 days"
auto_resolve: runway_days >= threshold
```

### Warning Runway Alert ⚠️
```yaml
condition:
  runway_days < config.burn_rate.runway_warning
  OR runway_decreased > 0.25  # 25% decrease

threshold:
  default: 60  # days
  decrease_threshold: 0.25

message: |
  ⚠️ WARNING: Runway decreasing
  - Current Runway: [X] days
  - Previous: [Y] days
  - Change: -[Z] days
  - Projected Depletion: [Date]
  - Recommendation: Increase emergency fund or reduce spending

trigger_frequency: "weekly"
auto_resolve: runway_days >= threshold
```

### Runway Opportunity 💡
```yaml
condition:
  runway_days >= config.burn_rate.runway_warning * 2
  AND emergency_fund < emergency_fund_target

message: |
  💡 OPPORTUNITY: Healthy runway - accelerate emergency fund
  - Current Runway: [X] days
  - Emergency Fund: $[Y] of $[Z] target
  - Suggestion: Allocate surplus to emergency fund

trigger_frequency: "monthly"
```

---

## Budget Alerts

### Critical Budget Alert 🚨
```yaml
condition:
  category_utilization >= config.budget.critical_threshold
  AND days_remaining >= 5

threshold:
  default: 0.95  # 95%
  configurable: true

message: |
  🚨 CRITICAL: Budget exceeded!
  - Category: [Category]
  - Used: [X]% ($[Y] of $[Z])
  - Days Remaining: [A]
  - Status: Over budget by $[B]
  - Action: STOP spending in this category

trigger_frequency: "on_transaction"
auto_resolve: new_month_started
```

### Warning Budget Alert ⚠️
```yaml
condition:
  category_utilization >= config.budget.warning_threshold
  OR (category_utilization / days_elapsed) * days_in_month > 1.0

threshold:
  default: 0.80  # 80%
  configurable: true

message: |
  ⚠️ WARNING: Approaching budget limit
  - Category: [Category]
  - Used: [X]% ($[Y] of $[Z])
  - Days Remaining: [A]
  - Pace: Projected [B]% by month end
  - Recommendation: Reduce spending in this category

trigger_frequency: "daily"
auto_resolve: category_utilization < threshold
```

### Budget Pacing Alert ⚠️
```yaml
condition:
  (category_spend / days_elapsed) * days_in_month > category_budget * 1.1

message: |
  ⚠️ WARNING: Spending pace too high
  - Category: [Category]
  - Current Pace: $[X]/day
  - Sustainable Pace: $[Y]/day
  - Projected Month Total: $[Z] (budget: $[A])
  - Overage: $[B]
  - Action: Reduce to $[Y]/day or less

trigger_frequency: "daily"
auto_resolve: pacing_corrected
```

### Budget Success Insight 📊
```yaml
condition:
  end_of_month
  AND all_categories_under_budget

message: |
  📊 INSIGHT: Perfect budget month!
  - All categories under budget
  - Surplus: $[X]
  - Celebrate this win!

trigger_frequency: "monthly"
```

---

## Debt Alerts

### Critical Debt Alert 🚨
```yaml
condition:
  debt_payment_due_date <= 1_day
  OR debt_payment_missed

threshold:
  urgent: 1  # day
  critical: 0  # overdue

message: |
  🚨 CRITICAL: Debt payment due NOW!
  - Debt: [Debt Name]
  - Amount: $[X]
  - Due: [Date/Time]
  - Status: [Due Today / OVERDUE]
  - Action: Make payment immediately to avoid fees

trigger_frequency: "hourly"
auto_resolve: payment_logged
```

### Warning Debt Alert ⚠️
```yaml
condition:
  debt_payment_due_date <= 7_days
  AND payment_not_made

threshold:
  week: 7    # days
  three_day: 3  # days

message: |
  ⚠️ WARNING: Upcoming debt payment
  - Debt: [Debt Name]
  - Amount: $[X]
  - Due: [Date] ([Y] days)
  - Reminder: Schedule this payment

trigger_frequency: "daily"
escalation: "increase frequency at 3 days and 1 day"
auto_resolve: payment_logged OR due_date_passed
```

### Debt Opportunity 💡
```yaml
condition:
  surplus_available >= min_debt_payment * 2
  AND debt_balance > 0

message: |
  💡 OPPORTUNITY: Extra debt payment available
  - Available: $[X] surplus
  - Recommended: Extra payment to [Debt Name]
  - Impact: Save $[Y] interest, payoff [Z] months sooner

trigger_frequency: "monthly"
```

### Debt Milestone Insight 📊
```yaml
condition:
  debt_milestone_reached
  # milestones: 25%, 50%, 75%, 100%, debt_eliminated

message: |
  📊 INSIGHT: Debt milestone achieved! 🎉
  - Debt: [Debt Name]
  - Milestone: [X]% paid off
  - Remaining: $[Y]
  - Original Balance: $[Z]
  - Keep up the great work!

trigger_frequency: "on_milestone"
```

---

## Goal Alerts

### Critical Goal Alert 🚨
```yaml
condition:
  goal_deadline <= 30_days
  AND goal_completion < 0.75  # Less than 75% complete

message: |
  🚨 CRITICAL: Goal deadline approaching!
  - Goal: [Goal Name]
  - Progress: [X]%
  - Target: $[Y]
  - Remaining: $[Z]
  - Deadline: [Date] ([A] days)
  - Required: $[B]/day to meet deadline
  - Action: Increase contributions or adjust deadline

trigger_frequency: "daily"
auto_resolve: goal_achieved OR deadline_extended
```

### Warning Goal Alert ⚠️
```yaml
condition:
  projected_completion_date > goal_deadline
  OR contribution_pace < required_pace

message: |
  ⚠️ WARNING: Goal behind schedule
  - Goal: [Goal Name]
  - Progress: [X]%
  - Current Pace: $[Y]/month
  - Required Pace: $[Z]/month
  - Shortfall: $[A]/month
  - Projected Completion: [Date] (vs target [Date])
  - Recommendation: Increase contributions by $[A]/month

trigger_frequency: "weekly"
auto_resolve: on_pace OR goal_achieved
```

### Goal Opportunity 💡
```yaml
condition:
  surplus_available
  AND goal_active
  AND goal_completion < 1.0

message: |
  💡 OPPORTUNITY: Surplus available for goals
  - Available: $[X]
  - Suggested Allocation:
    - [Goal 1]: $[Y] (would accelerate by [Z] days)
    - [Goal 2]: $[A] (would accelerate by [B] days)

trigger_frequency: "monthly"
```

### Goal Milestone Insight 📊
```yaml
condition:
  goal_milestone_reached
  # milestones: 10%, 25%, 50%, 75%, 100%

message: |
  📊 INSIGHT: Goal milestone achieved! 🎉
  - Goal: [Goal Name]
  - Milestone: [X]%
  - Balance: $[Y] of $[Z]
  - On Track: [Yes/No]
  - Excellent progress!

trigger_frequency: "on_milestone"
```

---

## Spending Pattern Alerts

### Critical Spending Leak Alert 🚨
```yaml
condition:
  leak_monthly_cost > 100
  AND leak_frequency = "daily" OR "multiple_daily"

threshold:
  high_impact: 100  # $/month
  very_frequent: "daily"

message: |
  🚨 CRITICAL: Major spending leak detected!
  - Pattern: [Description]
  - Frequency: [X] times/day
  - Cost: $[Y]/month ($[Z]/year)
  - Impact: [A]% of monthly budget
  - Action: Immediate elimination required

trigger_frequency: "weekly"
auto_resolve: leak_eliminated_7_days
```

### Warning Spending Leak Alert ⚠️
```yaml
condition:
  leak_monthly_cost > 30
  OR leak_frequency = "several_per_week"

threshold:
  medium_impact: 30  # $/month
  frequent: "multiple_weekly"

message: |
  ⚠️ WARNING: Spending leak identified
  - Pattern: [Description]
  - Frequency: [X]/week
  - Monthly Cost: $[Y]
  - Annual Impact: $[Z]
  - Recommendation: Consider eliminating or reducing

trigger_frequency: "weekly"
auto_resolve: leak_reduced_50_percent
```

### Anomaly Alert ⚠️
```yaml
condition:
  transaction_amount > (category_average * 2)
  OR unusual_vendor
  OR unusual_timing

threshold:
  anomaly_multiplier: 2.0  # 2x average

message: |
  ⚠️ WARNING: Unusual transaction detected
  - Amount: $[X]
  - Category: [Category]
  - Typical: $[Y] average
  - Variance: [Z]x higher
  - Vendor: [Vendor]
  - Note: Verify this transaction is correct

trigger_frequency: "on_transaction"
```

### Spending Insight 📊
```yaml
condition:
  category_trend_significant
  OR day_of_week_pattern_identified
  OR time_of_day_pattern_identified

message: |
  📊 INSIGHT: Spending pattern observed
  - Pattern: [Description]
  - Impact: [Quantified impact]
  - Observation: [Contextual insight]
  - Consider: [Relevant consideration]

trigger_frequency: "weekly"
```

---

## Emergency Fund Alerts

### Critical Emergency Fund Alert 🚨
```yaml
condition:
  emergency_fund < 1000
  OR emergency_fund < (monthly_expenses * 0.5)

threshold:
  absolute_minimum: 1000
  relative_minimum: 0.5  # months of expenses

message: |
  🚨 CRITICAL: Emergency fund dangerously low!
  - Balance: $[X]
  - Target: $[Y]
  - Coverage: [Z] days of expenses
  - Action: Prioritize emergency fund immediately

trigger_frequency: "daily"
auto_resolve: emergency_fund >= threshold
```

### Warning Emergency Fund Alert ⚠️
```yaml
condition:
  emergency_fund < (emergency_fund_target * 0.25)
  OR emergency_fund_decreased

threshold:
  target_percentage: 0.25  # 25% of target

message: |
  ⚠️ WARNING: Emergency fund below target
  - Balance: $[X]
  - Target: $[Y]
  - Progress: [Z]%
  - Recommendation: Allocate [A]% of income to emergency fund

trigger_frequency: "weekly"
auto_resolve: emergency_fund >= threshold
```

### Emergency Fund Opportunity 💡
```yaml
condition:
  emergency_fund >= emergency_fund_target
  AND surplus_available

message: |
  💡 OPPORTUNITY: Emergency fund fully funded!
  - Balance: $[X]
  - Target: $[Y] ✓
  - Suggestion: Redirect emergency fund contributions to:
    - Debt payoff, OR
    - Other goals, OR
    - Investment opportunities

trigger_frequency: "on_target_reached"
```

### Emergency Fund Milestone 📊
```yaml
condition:
  emergency_fund_milestone_reached
  # milestones: 25%, 50%, 75%, 100%

message: |
  📊 INSIGHT: Emergency fund milestone! 🎉
  - Milestone: [X]%
  - Balance: $[Y] of $[Z]
  - Coverage: [A] months of expenses
  - Excellent financial security progress!

trigger_frequency: "on_milestone"
```

---

## Compound Alerts

### Perfect Storm Alert 🚨
```yaml
condition:
  high_burn_rate
  AND low_runway
  AND upcoming_debt_payment
  AND over_budget_multiple_categories

message: |
  🚨 CRITICAL: Multiple financial pressures detected!
  - High burn rate: $[X]/day
  - Low runway: [Y] days
  - Upcoming payment: $[Z] in [A] days
  - Budget overruns: [B] categories
  - Action: EMERGENCY FINANCIAL REVIEW NEEDED
  - Recommendations:
    1. [Immediate action 1]
    2. [Immediate action 2]
    3. [Immediate action 3]

trigger_frequency: "daily"
priority: "maximum"
```

### Financial Health Warning ⚠️
```yaml
condition:
  (runway < 45 AND burn_rate_increasing)
  OR (multiple_budgets_over AND debt_payments_upcoming)
  OR (no_emergency_fund AND irregular_income)

message: |
  ⚠️ WARNING: Multiple financial health concerns
  - [List of active concerns]
  - Compound Risk: [Risk assessment]
  - Priority Actions:
    1. [Action 1]
    2. [Action 2]
  - Recommendation: Schedule financial review

trigger_frequency: "weekly"
```

### Positive Momentum Insight 📊
```yaml
condition:
  burn_rate_decreasing
  AND budget_adherence_improving
  AND (debt_decreasing OR goals_progressing)

message: |
  📊 INSIGHT: Strong financial momentum! 🎉
  - Burn rate: Decreasing [X]%
  - Budget adherence: [Y]% (improving)
  - Progress: [Debt/Goals update]
  - Keep up the excellent work!

trigger_frequency: "monthly"
```

---

## Alert Escalation Rules

### Escalation Triggers
```yaml
escalation_conditions:
  ignored_critical_alert:
    duration: 3_days
    action: "Increase notification frequency"
    new_frequency: "hourly"

  worsening_condition:
    condition: "metric_deteriorating_despite_alert"
    action: "Escalate priority level"
    message: "Previous alert unresolved and worsening"

  multiple_related_alerts:
    threshold: 3  # related alerts
    action: "Generate compound alert"
    message: "Multiple related concerns detected"

  approaching_deadline:
    thresholds: [30, 14, 7, 3, 1]  # days
    action: "Increase frequency and urgency"
```

### De-escalation Rules
```yaml
de_escalation_conditions:
  condition_improving:
    threshold: 0.20  # 20% improvement
    action: "Reduce frequency"
    message: "Positive progress on [alert]"

  alert_resolved:
    action: "Move to resolved section"
    archive_after: 30_days

  user_acknowledged:
    action: "Reduce notification frequency"
    new_frequency: "daily" # instead of multiple times
```

---

## Alert Grouping Rules

```yaml
grouping_rules:
  similar_alerts:
    condition: "same_category_multiple_alerts"
    action: "Combine into single alert"
    example: "Multiple budget warnings → Budget health summary"

  related_alerts:
    condition: "cascading_impact_alerts"
    action: "Group with primary cause highlighted"
    example: "High burn + low runway + budget over → Financial pressure alert"

  temporal_alerts:
    condition: "time_based_related_alerts"
    action: "Group by timeframe"
    example: "Multiple debt payments same week → Payment week alert"
```

---

## Alert Suppression Rules

```yaml
suppression_rules:
  duplicate_prevention:
    window: 24_hours
    action: "Don't re-alert for same condition within 24h"

  alert_fatigue:
    threshold: 10  # alerts per day
    action: "Consolidate into summary alert"

  temporary_condition:
    duration: 2_hours  # transient state
    action: "Don't alert if condition resolves within 2h"

  user_override:
    action: "Suppress specific alerts per user request"
    duration: "configurable"
    note: "Document reason for suppression"
```

---

## Alert Context Rules

```yaml
context_requirements:
  always_include:
    - Current state vs threshold
    - Trend direction (improving/worsening)
    - Specific recommended action
    - Impact quantification

  include_when_relevant:
    - Historical comparison
    - Related metrics
    - Alternative options
    - Timeline projection

  visualization:
    - Progress bars for percentages
    - Trend arrows for changes
    - Emoji indicators for severity
    - Tables for breakdowns
```

---

## Alert Testing Conditions

```yaml
test_alerts:
  daily_test:
    - Check all alert conditions
    - Verify thresholds still appropriate
    - Test escalation logic

  weekly_test:
    - Review resolved alerts
    - Analyze alert effectiveness
    - Adjust thresholds if needed

  monthly_test:
    - Full alert system review
    - Check for alert fatigue
    - Optimize grouping and suppression
```

---

These thresholds and rules provide comprehensive alert coverage while avoiding alert fatigue through intelligent grouping, escalation, and suppression. All thresholds are configurable via the config.md file.
