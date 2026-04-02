# Finance Buddy - Financial Calculations Reference

This document defines all financial calculations, formulas, and methodologies used by the finance-buddy skill.

---

## Burn Rate Calculations

### Daily Burn Rate
```
Daily Burn Rate = (Total Expenses - Total Income) / Number of Days

Components:
- Total Expenses: Sum of all expense transactions in period
- Total Income: Sum of all income transactions in period
- Number of Days: Calendar days in calculation period

Example:
- Period: 7 days
- Expenses: $850
- Income: $200
- Burn Rate: ($850 - $200) / 7 = $92.86/day
```

### Rolling Average Burn Rate
```
7-Day Rolling Burn Rate = Sum of last 7 days net expenses / 7
30-Day Rolling Burn Rate = Sum of last 30 days net expenses / 30

Purpose:
- 7-day: Short-term spending trends, immediate feedback
- 30-day: Long-term baseline, seasonal smoothing

Update Frequency: After each transaction or daily
```

### Adjusted Burn Rate (Excluding One-Time Events)
```
Adjusted Burn Rate = (Total Expenses - One-Time Expenses - Income) / Days

One-Time Expenses:
- Annual subscriptions
- Quarterly payments
- Emergency expenses
- Large unusual purchases

Purpose: More accurate sustainable burn rate calculation
```

### Burn Rate Trend
```
Trend Calculation:
- Current Period Burn Rate
- Previous Period Burn Rate
- Change = (Current - Previous) / Previous * 100

Trend Classification:
- Increasing: Change > +5%
- Stable: Change between -5% and +5%
- Decreasing: Change < -5%

Significance Threshold: ±15% (major trend)
```

---

## Runway Calculations

### Basic Runway
```
Runway (days) = Emergency Fund Balance / Daily Burn Rate

Example:
- Emergency Fund: $5,000
- Daily Burn Rate: $100/day
- Runway: 5,000 / 100 = 50 days
```

### Runway with Income
```
Runway with Income = Emergency Fund / (Daily Expenses - Daily Income)

Example:
- Emergency Fund: $5,000
- Daily Expenses: $120
- Daily Income: $50 (part-time/freelance)
- Runway: 5,000 / (120 - 50) = 71.4 days
```

### Projected Runway Depletion Date
```
Depletion Date = Current Date + Runway Days

Consider:
- Current trend (increasing/decreasing burn rate)
- Upcoming known expenses
- Expected income changes

Calculation:
- Conservative: Use 7-day burn rate (recent trend)
- Moderate: Use 30-day burn rate (balanced)
- Optimistic: Use adjusted burn rate (excluding anomalies)
```

### Runway Scenarios
```
Scenario Analysis:

Best Case:
- Burn Rate: -20% (reduction achieved)
- Income: +20% (increase achieved)
- Runway Extension: Calculate

Worst Case:
- Burn Rate: +20% (increase)
- Income: -20% (reduction)
- Runway Reduction: Calculate

Target Case:
- Burn Rate: As budgeted
- Income: As expected
- Runway: Baseline
```

---

## Budget Calculations

### Budget Utilization
```
Category Utilization = Category Spent / Category Budget * 100

Example:
- Category: Dining Out
- Spent: $180
- Budget: $200
- Utilization: 180 / 200 * 100 = 90%
```

### Budget Pace Analysis
```
Expected Pace = Days Elapsed / Days in Month * 100
Actual Pace = Amount Spent / Budget * 100

Pace Variance = Actual Pace - Expected Pace

Example (Day 15 of 30-day month):
- Expected Pace: 15 / 30 * 100 = 50%
- Actual Spending: $150 of $200 budget = 75%
- Pace Variance: 75% - 50% = +25% (spending too fast)

Interpretation:
- Positive Variance: Spending faster than calendar pace
- Negative Variance: Spending slower than calendar pace (good)
- Target: Actual ≤ Expected
```

### Projected End-of-Month Total
```
Projected Total = Current Spend / Days Elapsed * Days in Month

Example (Day 15 of 30):
- Current Spend: $150
- Projected: 150 / 15 * 30 = $300
- Budget: $200
- Projected Overage: $100

Alert Threshold: Projected > Budget * 1.05 (5% over)
```

### Daily Budget Remaining
```
Daily Budget Available = (Budget - Spent) / Days Remaining

Example:
- Budget: $200
- Spent: $150
- Days Remaining: 10
- Daily Available: (200 - 150) / 10 = $5/day

Purpose: Real-time spending guidance
```

### Budget Variance Analysis
```
Variance = Actual Spending - Budget
Variance % = Variance / Budget * 100

Classification:
- Under Budget: Variance < 0
- On Budget: Variance ≈ 0 (within 5%)
- Over Budget: Variance > 0

Significance:
- Minor: ±5%
- Moderate: ±10%
- Major: ±15%
```

---

## Debt Calculations

### Debt Payoff Timeline
```
Simple Interest:
Months to Payoff = Balance / Monthly Payment

Example:
- Balance: $5,000
- Payment: $250/month
- Timeline: 5,000 / 250 = 20 months

Compound Interest:
Months = -log(1 - (Balance * Monthly Rate / Payment)) / log(1 + Monthly Rate)

Where Monthly Rate = Annual Rate / 12

Example:
- Balance: $5,000
- Payment: $250/month
- Annual Rate: 18% (0.18)
- Monthly Rate: 0.015
- Months = -log(1 - (5000 * 0.015 / 250)) / log(1.015)
- Months ≈ 23 months
```

### Total Interest Paid
```
Total Interest = (Monthly Payment * Months to Payoff) - Starting Balance

Example:
- Balance: $5,000
- Payment: $250/month
- Months: 23
- Total Paid: 250 * 23 = $5,750
- Interest: 5,750 - 5,000 = $750
```

### Interest Savings from Extra Payment
```
Baseline Interest = Calculate with minimum payment
Accelerated Interest = Calculate with extra payment
Interest Savings = Baseline Interest - Accelerated Interest
Time Savings = Baseline Months - Accelerated Months

Example:
Minimum Payment ($100):
- Months: 40
- Interest: $2,000

With Extra $50:
- Payment: $150
- Months: 25
- Interest: $1,200
- Savings: $800 interest, 15 months
```

### Debt Avalanche Calculation
```
Method: Pay minimum on all debts, extra to highest interest rate

Ranking:
1. Sort debts by interest rate (highest first)
2. Apply all extra payments to #1
3. When #1 paid off, move to #2

Total Interest Calculation:
- Calculate each debt payoff individually
- Sum all interest paid
- Compare to other strategies

Optimal for: Minimizing total interest paid
```

### Debt Snowball Calculation
```
Method: Pay minimum on all debts, extra to smallest balance

Ranking:
1. Sort debts by balance (smallest first)
2. Apply all extra payments to #1
3. When #1 paid off, roll payment to #2

Total Interest Calculation:
- Calculate each debt payoff individually
- Sum all interest paid
- Compare to avalanche strategy

Optimal for: Psychological wins, momentum building

Interest Cost vs Avalanche: Typically +5-15% more interest
```

### Debt Payment Allocation
```
Minimum Total = Sum of all minimum payments

Extra Payment Allocation:

Avalanche:
- Debt with highest rate gets: Extra Payment + Minimum
- All others: Minimum only

Snowball:
- Debt with smallest balance gets: Extra Payment + Minimum
- All others: Minimum only

Proportional (Alternative):
- Extra allocated by balance percentage
- Debt 1: (Balance1 / Total Balance) * Extra Payment
```

### Debt-to-Income Ratio
```
DTI Ratio = Total Monthly Debt Payments / Monthly Gross Income * 100

Example:
- Debt Payments: $800/month
- Income: $4,000/month
- DTI: 800 / 4,000 * 100 = 20%

Categories:
- Excellent: < 20%
- Good: 20-35%
- Fair: 36-49%
- Poor: ≥ 50%
```

---

## Goal Calculations

### Goal Progress
```
Progress = Current Balance / Target Amount * 100

Example:
- Current: $2,500
- Target: $10,000
- Progress: 2,500 / 10,000 * 100 = 25%
```

### Required Monthly Contribution
```
Required Monthly = (Target - Current) / Months Remaining

Example:
- Target: $10,000
- Current: $2,500
- Remaining: $7,500
- Months to Deadline: 15
- Required: 7,500 / 15 = $500/month
```

### Projected Completion Date
```
Based on Current Pace:
Projected Months = (Target - Current) / Average Monthly Contribution
Completion Date = Current Date + Projected Months

Example:
- Remaining: $7,500
- Average Contribution: $300/month (actual pace)
- Months: 7,500 / 300 = 25 months
- Completion: 25 months from now

Comparison to Deadline: [On Track / Behind / Ahead]
```

### Contribution Pace Analysis
```
Required Pace = Required Monthly Contribution
Actual Pace = Average of last 3 months contributions

Pace Variance = Actual Pace - Required Pace

Example:
- Required: $500/month
- Actual: $350/month
- Variance: -$150/month (behind pace)

Impact: Will miss deadline by X months
Adjustment Needed: Increase by $150/month
```

### Goal Priority Score
```
Priority Score = (Deadline Urgency * Weight1) +
                 (Importance Level * Weight2) +
                 (Financial Impact * Weight3)

Deadline Urgency:
- < 3 months: 10 points
- 3-6 months: 7 points
- 6-12 months: 5 points
- > 12 months: 3 points

Importance:
- Critical: 10 points
- High: 7 points
- Medium: 5 points
- Low: 3 points

Use: Recommend allocation priority when multiple goals active
```

### Goal Milestone Dates
```
Milestones: 25%, 50%, 75%, 100%

Calculate for each milestone:
Amount Needed = Target * Milestone Percentage
Remaining to Milestone = Amount Needed - Current Balance
Months to Milestone = Remaining / Average Monthly Contribution
Milestone Date = Current Date + Months

Example (50% milestone):
- Target: $10,000
- Current: $2,500
- 50% Target: $5,000
- Remaining: $2,500
- Monthly: $300
- Months: 8.3
- Date: ~8 months from now
```

---

## Emergency Fund Calculations

### Emergency Fund Target
```
Method 1: Months of Expenses
Target = Monthly Expenses * Target Months

Example:
- Monthly Expenses: $3,000
- Target: 6 months
- Emergency Fund Target: $18,000

Method 2: Multiple of Burn Rate
Target = Daily Burn Rate * 180 (days)

Recommended Targets:
- Single, stable job: 3-6 months
- Married, dual income: 3-6 months
- Single income family: 6-9 months
- Self-employed: 9-12 months
```

### Emergency Fund Progress
```
Progress = Current Balance / Target * 100
Coverage = Current Balance / Monthly Expenses (in months)

Example:
- Balance: $9,000
- Target: $18,000
- Monthly Expenses: $3,000
- Progress: 50%
- Coverage: 3 months
```

### Emergency Fund Adequacy Score
```
Score = (Coverage Months / Target Months) * 100

Benchmarks:
- 0-25%: Critical - Inadequate protection
- 25-50%: Warning - Building protection
- 50-75%: Good - Moderate protection
- 75-100%: Excellent - Strong protection
- 100%+: Optimal - Fully protected
```

---

## Spending Pattern Calculations

### Spending Leak Detection
```
Leak Identification:
1. Group transactions by similar characteristics
   - Same vendor, multiple occurrences
   - Same category, small amounts, high frequency
   - Similar description patterns

2. Calculate leak cost:
   Frequency = Transactions / Days * 30 (monthly)
   Monthly Cost = Average Transaction * Frequency
   Annual Impact = Monthly Cost * 12

Example:
- Daily coffee: $5
- Frequency: 20 days/month
- Monthly: $5 * 20 = $100
- Annual: $1,200

Threshold for Alert:
- Low Impact: < $30/month
- Medium Impact: $30-$100/month
- High Impact: > $100/month
```

### Spending Anomaly Detection
```
Anomaly = Transaction significantly different from pattern

Statistical Method:
Mean = Average transaction in category
Std Dev = Standard deviation of transactions
Z-Score = (Transaction - Mean) / Std Dev

Anomaly if Z-Score > 2 (2 standard deviations)

Simple Method:
Anomaly if Transaction > (Category Average * 2)

Example:
- Category Average: $30
- This Transaction: $75
- Ratio: 2.5x
- Classification: Anomaly ⚠️
```

### Category Trend Analysis
```
Trend = Compare periods

Month-over-Month:
Change = (This Month - Last Month) / Last Month * 100

Example:
- Last Month: $400
- This Month: $480
- Change: (480 - 400) / 400 * 100 = +20%

Trend Significance:
- Minor: ±10%
- Moderate: ±20%
- Major: ±30%
```

### Day-of-Week Spending Pattern
```
For each day of week:
Average Spending = Sum of all [Day] transactions / Number of [Days]

Example (Saturdays):
- Total Saturday Spending: $600 (over 4 Saturdays)
- Average: $600 / 4 = $150/Saturday

Compare to overall daily average:
Variance = (Day Average - Overall Average) / Overall Average * 100

Insight: Identify high-spending days
```

### Time-of-Day Patterns
```
Segments:
- Morning: 6am-12pm
- Afternoon: 12pm-6pm
- Evening: 6pm-12am
- Night: 12am-6am

For each segment:
Total Spending = Sum of transactions in segment
Percentage = Segment Total / Daily Total * 100

Insights:
- Identify impulse spending times
- Recognize routine patterns
- Optimize spending timing
```

---

## Comparative Calculations

### Budget Adherence Score
```
Category Scores:
- Under budget: 10 points
- Within 5% of budget: 8 points
- Within 10% of budget: 6 points
- Within 20% of budget: 4 points
- Over 20%: 0 points

Overall Score = Average of all category scores

Example:
- 5 categories under budget: 50 points
- 2 categories within 5%: 16 points
- 1 category within 10%: 6 points
- Total: 72 / 8 categories = 9.0/10

Rating:
- 9-10: Excellent
- 7-8.9: Good
- 5-6.9: Fair
- <5: Poor
```

### Financial Health Score
```
Components (weighted):
1. Runway Health (30%)
   - > 90 days: 10 points
   - 60-90 days: 7 points
   - 30-60 days: 4 points
   - < 30 days: 0 points

2. Budget Adherence (25%)
   - Use Budget Adherence Score

3. Debt Load (20%)
   - DTI < 20%: 10 points
   - DTI 20-35%: 7 points
   - DTI 36-49%: 4 points
   - DTI ≥ 50%: 0 points

4. Emergency Fund (15%)
   - 100%+ funded: 10 points
   - 75-99%: 7 points
   - 50-74%: 5 points
   - 25-49%: 3 points
   - <25%: 0 points

5. Savings Rate (10%)
   - > 20%: 10 points
   - 15-20%: 7 points
   - 10-15%: 5 points
   - 5-10%: 3 points
   - < 5%: 0 points

Overall Score = Weighted sum
Rating: Same as Budget Adherence
```

### Month-over-Month Comparison
```
Metrics to Compare:
1. Total Spending
2. Spending by Category
3. Burn Rate
4. Budget Adherence
5. Savings Rate
6. Goal Progress
7. Debt Payoff
8. Emergency Fund Growth

For each metric:
Change = (Current - Previous) / Previous * 100
Trend Direction = Improving / Worsening / Stable

Improvement Indicators:
- Spending: Decreasing
- Burn Rate: Decreasing
- Budget Adherence: Increasing
- Savings: Increasing
- Goals: Increasing
- Debt: Decreasing (balance)
- Emergency Fund: Increasing
```

### Savings Rate Calculation
```
Savings Rate = (Income - Expenses) / Income * 100

Include in Savings:
- Emergency fund contributions
- Goal contributions
- Investment contributions
- Debt principal payments (optional)

Exclude from Savings:
- Debt interest payments

Example:
- Income: $4,000
- Expenses: $3,000
- Savings: $1,000
- Rate: 1,000 / 4,000 * 100 = 25%

Benchmarks:
- Excellent: > 20%
- Good: 15-20%
- Fair: 10-15%
- Poor: < 10%
- Negative: Spending > Income
```

---

## Optimization Calculations

### Cost-Benefit Analysis
```
For any spending reduction or elimination:

Annual Savings = Monthly Cost * 12
Runway Extension = Annual Savings / Daily Burn Rate

Quality of Life Impact:
- High impact: Significant life quality reduction
- Medium impact: Noticeable but manageable
- Low impact: Minimal life quality change

Optimization Score = Savings / (Quality of Life Impact + 1)

Priority: High score = High priority for optimization
```

### Budget Reallocation Analysis
```
When reallocating between categories:

Freed Amount = Reduction in Category A
Needed Amount = Increase in Category B

Feasibility = Freed Amount >= Needed Amount

Impact Assessment:
- Category A: Can reduce without hardship?
- Category B: Will increase solve problem?
- Net Benefit: Positive budget change?

Example:
- Reduce Dining Out by $100
- Increase Groceries by $100
- Net Change: $0
- Benefit: Likely reduced overall food cost
```

### Goal Allocation Optimization
```
When multiple goals compete for funds:

For each goal:
- Urgency Score (deadline-based)
- Impact Score (importance-based)
- Progress Score (how close to completion)

Priority = (Urgency * 0.4) + (Impact * 0.3) + (Progress * 0.3)

Allocation Strategy:
1. Meet minimum contributions for all
2. Allocate surplus by priority score
3. Bonus for goals near milestones
```

---

## Calculation Notes

### Precision and Rounding
- Currency: Round to 2 decimal places
- Percentages: Round to 1 decimal place
- Days/Months: Round to nearest whole number for display
- Store full precision internally

### Date Calculations
- Use actual calendar days
- Account for month length variations
- Consider partial months in projections

### Edge Cases
- Division by zero: Handle gracefully (show "N/A" or "--")
- Negative values: Mark clearly in displays
- Missing data: Use available data, note limitations
- Outliers: Consider adjusted calculations

### Update Frequency
- Burn Rate: Real-time (after each transaction)
- Runway: Real-time (whenever burn rate or emergency fund changes)
- Budget: Real-time (after each transaction)
- Goals: Real-time (after contributions)
- Debt: After each payment
- Trends: Daily recalculation
- Patterns: Weekly analysis

---

All calculations should be transparent, explainable, and verifiable by the user. When displaying calculations, show the formula and inputs used to build trust and understanding.
