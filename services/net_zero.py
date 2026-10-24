from datetime import datetime

def calculate_net_zero_plan(baseline_emission, target_reduction_pct, target_year, current_annual_emission=None):
    if baseline_emission <= 0:
        raise ValueError("Baseline emission must be positive")
    if not (0 < target_reduction_pct <= 100):
        raise ValueError("Target reduction percentage must be between 1 and 100")
        
    current_year = datetime.now().year
    if target_year <= current_year:
        raise ValueError("Target year must be in the future")
        
    target_emission = round(baseline_emission * (1 - target_reduction_pct / 100), 2)
    required_reduction = round(baseline_emission - target_emission, 2)
    years_remaining = target_year - current_year
    annual_reduction_needed = round(required_reduction / years_remaining, 2)
    
    progress_pct = None
    on_track = None
    
    if current_annual_emission is not None:
        reduction_achieved = baseline_emission - current_annual_emission
        if required_reduction > 0:
            progress_pct = round(max(0, (reduction_achieved / required_reduction) * 100), 2)
        else:
            progress_pct = 100.0
            
        # simple check for on_track
        expected_reduction = (baseline_emission - current_annual_emission) / required_reduction if required_reduction else 1
        # naive check if progress matches expected yearly progress
        on_track = progress_pct >= ((1 / years_remaining) * 100) # Simplified logic
        
    phases = generate_roadmap_phases(baseline_emission, target_emission, target_year)
        
    return {
        'baseline': baseline_emission,
        'target_reduction_pct': target_reduction_pct,
        'target_emission': target_emission,
        'required_reduction': required_reduction,
        'target_year': target_year,
        'years_remaining': years_remaining,
        'annual_reduction_needed': annual_reduction_needed,
        'current_emission': current_annual_emission,
        'progress_pct': progress_pct,
        'on_track': on_track,
        'phases': phases
    }

def generate_roadmap_phases(baseline, target, target_year, category_breakdown=None):
    return [
        {
            'phase': 1,
            'title': 'Measurement & Baseline',
            'description': 'Establish a comprehensive baseline of current emissions across all scopes.',
            'timeline': 'Months 1-3',
            'actions': ['Implement tracking system', 'Audit historical data']
        },
        {
            'phase': 2,
            'title': 'Quick Wins & Efficiency',
            'description': 'Target low-hanging fruit to immediately reduce emissions and save costs.',
            'timeline': 'Months 4-12',
            'actions': ['Energy efficiency upgrades', 'Waste reduction programs']
        },
        {
            'phase': 3,
            'title': 'Core Infrastructure Changes',
            'description': 'Begin shifting major systems to low-carbon alternatives.',
            'timeline': 'Year 2-3',
            'actions': ['Transition to renewable energy', 'Fleet electrification planning']
        },
        {
            'phase': 4,
            'title': 'Deep Decarbonization',
            'description': 'Tackle hard-to-abate emissions and optimize supply chain.',
            'timeline': f'Years 4 to {target_year - 1}',
            'actions': ['Full fleet electrification', 'Supplier engagement for Scope 3']
        },
        {
            'phase': 5,
            'title': 'Net Zero & Maintenance',
            'description': 'Achieve net zero state and maintain through continuous monitoring and offsets for residual emissions.',
            'timeline': f'Year {target_year} and beyond',
            'actions': ['Purchase high-quality carbon offsets', 'Continuous system optimization']
        }
    ]
