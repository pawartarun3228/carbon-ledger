"""Scenario Simulation and Net-Zero Trajectory Engine.
Simulates activity-level decarbonization interventions across electricity, fuel, and transport.
Recalculates carbon impact using real underlying emission factors and projects annual glide-path trajectories.
"""

from datetime import datetime
from services.factor_registry import kg_to_tonnes
from services.net_zero import calculate_net_zero_plan, generate_roadmap_phases

def simulate_decarbonization_scenario(baseline_emissions_dict, target_reduction_pct, target_year,
                                     elec_reduction_pct=0.0, fuel_reduction_pct=0.0, transport_reduction_pct=0.0):
    """Recalculates organizational emissions under specified category intervention percentages.
    
    Args:
        baseline_emissions_dict (dict): Dictionary with keys 'electricity', 'fuel', 'transportation', 'other' (in kg CO2e)
        target_reduction_pct (float): Target overall reduction (1-100%)
        target_year (int): Target target year (> current year)
        elec_reduction_pct (float): Simulated reduction in electricity consumption (0-100%)
        fuel_reduction_pct (float): Simulated reduction in direct fuel consumption (0-100%)
        transport_reduction_pct (float): Simulated reduction in transport/commuting (0-100%)
        
    Returns:
        dict: Scenario outcomes, savings, remaining gap to target, and trajectory pathway.
    """
    elec_base = float(baseline_emissions_dict.get('electricity', 0.0))
    fuel_base = float(baseline_emissions_dict.get('fuel', 0.0))
    trans_base = float(baseline_emissions_dict.get('transportation', 0.0))
    other_base = float(baseline_emissions_dict.get('other', 0.0))
    
    total_baseline = elec_base + fuel_base + trans_base + other_base
    if total_baseline <= 0:
        total_baseline = 1.0 # Guard against division by zero

    # Constrain reduction percentages
    elec_r = max(0.0, min(100.0, float(elec_reduction_pct)))
    fuel_r = max(0.0, min(100.0, float(fuel_reduction_pct)))
    trans_r = max(0.0, min(100.0, float(transport_reduction_pct)))

    # Activity-based recalculation
    elec_scenario = elec_base * (1.0 - elec_r / 100.0)
    fuel_scenario = fuel_base * (1.0 - fuel_r / 100.0)
    trans_scenario = trans_base * (1.0 - trans_r / 100.0)
    other_scenario = other_base # Unabated
    
    total_scenario = round(elec_scenario + fuel_scenario + trans_scenario + other_scenario, 2)
    total_savings = round(total_baseline - total_scenario, 2)
    actual_scenario_pct = round((total_savings / total_baseline) * 100.0, 1)

    # Net-zero target computation
    plan = calculate_net_zero_plan(total_baseline, target_reduction_pct, target_year, current_annual_emission=total_scenario)
    target_emissions = plan['target_emission']
    remaining_gap = round(max(0.0, total_scenario - target_emissions), 2)
    target_achieved = total_scenario <= target_emissions

    # Annual Trajectory Modeling (Glide Path)
    current_year = datetime.now().year
    years_span = max(1, target_year - current_year)
    
    trajectory = []
    for step, yr in enumerate(range(current_year, target_year + 1)):
        fraction = step / years_span
        # Linear policy benchmark from baseline to target allowance
        benchmark_val = round(total_baseline - (fraction * plan['required_reduction']), 2)
        # Expected scenario glide path if interventions phase in smoothly
        scenario_val = round(total_baseline - (fraction * total_savings), 2)
        
        trajectory.append({
            'year': yr,
            'target_allowance_kg': benchmark_val,
            'scenario_projected_kg': scenario_val,
            'target_allowance_t': kg_to_tonnes(benchmark_val),
            'scenario_projected_t': kg_to_tonnes(scenario_val)
        })

    return {
        'baseline_total_kg': round(total_baseline, 2),
        'baseline_total_t': kg_to_tonnes(total_baseline),
        'scenario_total_kg': total_scenario,
        'scenario_total_t': kg_to_tonnes(total_scenario),
        'savings_kg': total_savings,
        'savings_t': kg_to_tonnes(total_savings),
        'savings_pct': actual_scenario_pct,
        'target_emissions_kg': target_emissions,
        'target_emissions_t': kg_to_tonnes(target_emissions),
        'remaining_gap_kg': remaining_gap,
        'remaining_gap_t': kg_to_tonnes(remaining_gap),
        'target_achieved': target_achieved,
        'breakdown': {
            'electricity': {'baseline': round(elec_base, 2), 'scenario': round(elec_scenario, 2), 'reduction_pct': elec_r},
            'fuel': {'baseline': round(fuel_base, 2), 'scenario': round(fuel_scenario, 2), 'reduction_pct': fuel_r},
            'transportation': {'baseline': round(trans_base, 2), 'scenario': round(trans_scenario, 2), 'reduction_pct': trans_r},
            'other': {'baseline': round(other_base, 2), 'scenario': round(other_scenario, 2), 'reduction_pct': 0.0}
        },
        'trajectory': trajectory,
        'phases': plan['phases'],
        'disclaimer': (
            "Scenario Planning Disclaimer: Results are indicative mathematical estimates based on current emission factors and reported baseline data. "
            "They do not constitute guaranteed savings or regulatory certification."
        )
    }
