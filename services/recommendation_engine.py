"""Explainable Recommendation Engine.
Analyzes the organization's verified carbon inventory and monthly trajectories
to deliver rule-based, transparent, and prioritized decarbonization strategies.
Does not claim guaranteed savings or label rule heuristics as machine learning.
"""

def _classify_impact(percentage):
    """Classify impact level and priority based on emission percentage.
    Returns a tuple of (impact_level, priority).
    """
    if percentage >= 60:
        return ('Very High Impact', 'CRITICAL')
    elif percentage >= 40:
        return ('High Impact', 'HIGH')
    elif percentage >= 20:
        return ('Moderate Impact', 'MEDIUM')
    else:
        return ('Low Impact', 'LOW')

def _get_recommendations_for_category(category_group, percentage):
    """Returns practical actions for the category."""
    tips = {
        'electricity': [
            'Switch to LED bulbs to reduce lighting energy consumption by up to 80%.',
            'Implement smart power strips to prevent phantom load from electronics.',
            'Upgrade to energy-efficient appliances (Energy Star rated).',
            'Utilize natural light during the day instead of artificial lighting.',
            'Adjust thermostat settings: a few degrees can save significant energy.',
            'Consider installing solar panels to generate renewable energy locally.'
        ],
        'fuel': [
            'Optimize driving routes to reduce mileage and save fuel.',
            'Maintain proper tire pressure to improve fuel efficiency.',
            'Avoid excessive idling; turn off the engine if stopped for over a minute.',
            'Remove excess weight from the vehicle to reduce drag.',
            'Switch to a more fuel-efficient or hybrid vehicle if possible.',
            'Consolidate trips and errands to minimize overall driving time.'
        ],
        'transportation': [
            'Promote carpooling or ride-sharing among colleagues or friends.',
            'Utilize public transportation (buses, trains) whenever feasible.',
            'Encourage active transport such as walking or cycling for short trips.',
            'Consider remote work or telecommuting options a few days a week.',
            'Incentivize the use of electric vehicles (EVs) over traditional combustion engines.',
            'Plan meetings virtually instead of traveling long distances.'
        ]
    }
    return tips.get(category_group, ['Monitor and reduce usage where possible.'])

def generate_recommendations(emission_records):
    """Generates explainable, evidence-backed decarbonization recommendations.
    
    Args:
        emission_records (list): List of emission record dicts.
        
    Returns:
        list: Ordered recommendations with evidence, rationale, estimated potential, and assumptions.
    """
    if not emission_records:
        return []
        
    total_emission = sum(float(r.get('co2e', 0.0)) for r in emission_records)
    if total_emission <= 0:
        return []

    # Group emissions
    grouped_emissions = {'electricity': 0.0, 'fuel': 0.0, 'transportation': 0.0, 'other': 0.0}
    cat_emissions = {}
    for r in emission_records:
        cat = r.get('category', 'unknown')
        val = float(r.get('co2e', 0.0))
        cat_emissions[cat] = cat_emissions.get(cat, 0.0) + val
        
        if cat == 'electricity':
            grouped_emissions['electricity'] += val
        elif cat in ('petrol', 'diesel'):
            grouped_emissions['fuel'] += val
        elif cat.startswith('transport_'):
            grouped_emissions['transportation'] += val
        else:
            grouped_emissions['other'] += val

    recommendations = []
    num_records = len(emission_records)
    confidence_level = "High" if num_records >= 12 else ("Moderate" if num_records >= 5 else "Preliminary")

    group_name_map = {
        'electricity': 'Electricity',
        'fuel': 'Fuel',
        'transportation': 'Transportation'
    }

    # Category-specific heuristics
    strategy_details = {
        'electricity': {
            'rationale': "Scope 2 grid electricity represents indirect emissions from facility lighting, computing, and thermal comfort systems.",
            'est_pct_reduction': 15.0,
            'difficulty': 'Medium',
            'assumptions': "Assumes 10-15% conservation through HVAC thermostat setpoint optimization (+2°C in summer), scheduled equipment shutdowns, and occupancy-sensed LED lighting retrofits.",
            'actions': [
                {'step': 'Conduct evening energy audit to identify baseload and phantom draw.', 'timeline': 'Week 1-2'},
                {'step': 'Implement automated HVAC scheduling aligned with campus operating hours.', 'timeline': 'Month 1'},
                {'step': 'Procure renewable energy certificates (RECs) or evaluate rooftop solar feasibility.', 'timeline': 'Month 3-6'}
            ]
        },
        'fuel': {
            'rationale': "Scope 1 stationary combustion (generators) and mobile combustion (fleet vehicles) generate direct tailpipe emissions.",
            'est_pct_reduction': 20.0,
            'difficulty': 'Low to Medium',
            'assumptions': "Assumes 15-20% fuel savings through aggressive route optimization, strict anti-idling policies, and routine engine tune-ups.",
            'actions': [
                {'step': 'Adopt telematics or GPS route consolidation for department transport vehicles.', 'timeline': 'Month 1'},
                {'step': 'Enforce a 60-second engine shutoff policy in campus loading zones.', 'timeline': 'Immediate'},
                {'step': 'Establish fleet electrification schedule for retiring internal combustion vehicles.', 'timeline': 'Year 1-2'}
            ]
        },
        'transportation': {
            'rationale': "Scope 3 employee commuting and organizational travel contribute substantially to community-wide mobility impacts.",
            'est_pct_reduction': 25.0,
            'difficulty': 'Medium',
            'assumptions': "Assumes modal shift from single-occupancy vehicles to public transit, cycling, and 1-2 remote work days weekly.",
            'actions': [
                {'step': 'Subsidize municipal transit passes and establish dedicated carpool matching.', 'timeline': 'Month 1-2'},
                {'step': 'Provide secure bicycle shelters, maintenance stands, and shower facilities.', 'timeline': 'Month 3'},
                {'step': 'Institute department-level telecommuting policy for eligible administrative roles.', 'timeline': 'Month 1'}
            ]
        }
    }

    for group, emission in grouped_emissions.items():
        if emission > 0 and group != 'other':
            pct = (emission / total_emission) * 100.0
            impact, priority = _classify_impact(pct)
            strat = strategy_details.get(group, {})
            est_pct = strat.get('est_pct_reduction', 10.0)
            est_kg = round(emission * (est_pct / 100.0), 2)

            recommendations.append({
                'source': group_name_map[group],
                'category_group': group,
                'emission': round(emission, 2),
                'percentage': round(pct, 1),
                'impact_level': impact,
                'priority': priority,
                'explanation': f'{group_name_map[group]} contributes {round(pct, 1)}% of your recorded emissions.',
                'tips': _get_recommendations_for_category(group, pct),
                # Extended explainability fields
                'observed_evidence': f"{group_name_map[group]} accounts for {round(pct, 1)}% ({round(emission, 1)} kg CO2e) of the total carbon inventory.",
                'why_suggested': strat.get('rationale', "Category represents a substantial portion of organizational carbon footprint."),
                'estimated_savings_kg': est_kg,
                'estimated_savings_tonnes': round(est_kg / 1000.0, 3),
                'estimated_savings_pct': est_pct,
                'assumptions': strat.get('assumptions', "Estimated based on industry benchmark conservation measures."),
                'difficulty': strat.get('difficulty', 'Medium'),
                'confidence': confidence_level,
                'action_steps': strat.get('actions', [])
            })

    # Detect Rising Emissions Trend (Month-over-month)
    monthly_map = {}
    for r in emission_records:
        if r.get('date'):
            m = str(r['date'])[:7]
            monthly_map[m] = monthly_map.get(m, 0.0) + float(r.get('co2e', 0.0))
        
    sorted_m = sorted(monthly_map.keys())
    if len(sorted_m) >= 2:
        last_m = sorted_m[-1]
        prev_m = sorted_m[-2]
        delta = monthly_map[last_m] - monthly_map[prev_m]
        if delta > 0 and monthly_map[prev_m] > 0:
            growth_pct = round((delta / monthly_map[prev_m]) * 100.0, 1)
            if growth_pct >= 5.0:
                recommendations.append({
                    'source': 'Trajectory Alert',
                    'category_group': 'trend',
                    'emission': round(delta, 2),
                    'percentage': growth_pct,
                    'impact_level': 'Trajectory Risk',
                    'priority': 'HIGH' if growth_pct >= 15.0 else 'MEDIUM',
                    'explanation': f"Emissions rose by {growth_pct}% between {prev_m} ({round(monthly_map[prev_m], 1)} kg) and {last_m} ({round(monthly_map[last_m], 1)} kg).",
                    'tips': [
                        f"Review recent activity records in {last_m} to pinpoint specific drivers of the {growth_pct}% increase.",
                        "Verify whether seasonal weather (high summer cooling or winter heating) explains the variance.",
                        "Inspect utility bills for billing adjustments or estimated meter readings."
                    ],
                    'observed_evidence': f"Net monthly emissions expanded from {round(monthly_map[prev_m], 1)} kg in {prev_m} to {round(monthly_map[last_m], 1)} kg in {last_m} (+{round(delta, 1)} kg CO2e).",
                    'why_suggested': "Sudden upward trajectory risks breaching annual reduction targets and indicates operational deviation.",
                    'estimated_savings_kg': round(delta, 2),
                    'estimated_savings_tonnes': round(delta / 1000.0, 3),
                    'estimated_savings_pct': growth_pct,
                    'assumptions': "Assumes emissions can be brought back to the previous baseline level.",
                    'difficulty': 'Low',
                    'confidence': confidence_level,
                    'action_steps': [
                        {'step': 'Inspect metering logs for uncharacteristic overnight baseload spikes.', 'timeline': 'Immediate'},
                        {'step': 'Engage facility technicians to audit HVAC dampers and thermostat schedules.', 'timeline': 'Week 1'}
                    ]
                })

    # Sort by percentage descending
    recommendations.sort(key=lambda x: x['percentage'], reverse=True)
    return recommendations
