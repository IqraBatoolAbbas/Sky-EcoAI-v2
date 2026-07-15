# Disruption Recovery Playbook

## Vehicle breakdown
When a vehicle breaks down, Sky.EcoAI marks it inactive, sets its assigned deliveries to at-risk, and regenerates Economy/Green/Service recovery plans using remaining active vehicles. The Service plan is often recommended when multiple orders are at risk.

## Urgent order
Urgent high-priority orders are inserted as at-risk with a tighter deadline. Re-optimize or run recovery so the dispatcher can slot them into a feasible route without dropping capacity constraints.

## Road blockage
Road blockage applies a geographic penalty near a coordinate radius and marks nearby orders at-risk. Recovery replans around affected stops.

## Range or low fuel warning
Electric or hybrid vehicles with critically low range are flagged. Their deliveries may need reassignment to another vehicle with sufficient capacity and range.

## How autonomous recovery works
Observe event → identify affected orders → call deterministic OR-Tools optimizer → score plans on cost, emissions, distance, and unassigned penalties → recommend best plan → update map/KPIs → log an explainable agent decision.

## Agent decision timeline
Each optimize/recovery/apply stores: trigger, alternatives evaluated, selected plan metrics, explanation text, and approval status (pending, approved, or auto_applied).
