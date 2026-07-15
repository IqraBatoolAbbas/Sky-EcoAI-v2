# Fleet Control Tower — Operator Guide

## What Sky.EcoAI Control Tower does
Sky.EcoAI is an autonomous green fleet control tower. It plans multi-vehicle delivery routes for Lahore, balances cost and estimated CO2e, detects disruptions, generates recovery plans, and explains decisions via the Fleet Copilot.

## Demo loop judges should see
1. Open Control Tower and review Operations Overview KPIs.
2. In Optimization Studio, generate Economy, Green, and Service plans, then Apply a plan.
3. In Event Center, trigger a vehicle breakdown for a vehicle carrying deliveries.
4. Generate recovery plans and apply the recommended plan (or enable Auto-apply).
5. Ask Fleet Copilot why the plan was selected and request a greener alternative.
6. End on Impact Report with kilometres, cost, estimated emissions, and protected deliveries.

## Planning modes explained
- Economy: prioritizes lower operating cost (PKR per km).
- Green: prefers hybrid and electric vehicles to reduce estimated CO2e.
- Service: prioritizes covering deliveries and protecting deadlines / at-risk orders.

## Carbon and cost labels
All CO2 values are estimates based on configured grams-per-km factors (petrol 192, hybrid 108, electric 48). Operating cost uses each vehicle's cost_per_km. Always say "estimated CO2e" in operator communications.

## Reset demo
Use Reset demo to reload the seeded Lahore scenario: 6 vehicles at Lahore Central Depot and 12 delivery orders across Gulberg, DHA, Model Town, Cantt, Airport, and surrounding areas.
