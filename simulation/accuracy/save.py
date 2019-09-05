import multiprocessing  # for using multiprocessing logger

import util.logging

import measurements.all.data

import simulation.accuracy.linearized
import simulation.model.save


def save(cost_function_name,
         model_name, time_step=1, concentrations=None, concentrations_index=None, parameters=None, parameter_set_index=None,
         spinup_years=None, spinup_tolerance=None, spinup_satisfy_years_and_tolerance=True, derivative_years=None, derivative_step_size=None, derivative_accuracy_order=None,
         model_parameters_relative_tolerance=None, model_parameters_absolute_tolerance=None, initial_concentrations_relative_tolerance=None, initial_concentrations_absolute_tolerance=None,
         min_measurements_standard_deviations=None, min_standard_deviations=None, min_measurements_correlations=None, correlation_decomposition_min_value_D=None, max_box_distance_to_water=None,
         alpha=0.99, time_dim_model=None, parallel=True):

    # prepare model options
    model_options = simulation.model.save.prepare_model_options(
        model_name, time_step=time_step, concentrations=concentrations, concentrations_index=concentrations_index, parameters=parameters, parameter_set_index=parameter_set_index,
        spinup_years=spinup_years, spinup_tolerance=spinup_tolerance, spinup_satisfy_years_and_tolerance=spinup_satisfy_years_and_tolerance,
        derivative_years=derivative_years, derivative_step_size=derivative_step_size, derivative_accuracy_order=derivative_accuracy_order,
        model_parameters_relative_tolerance=model_parameters_relative_tolerance, model_parameters_absolute_tolerance=model_parameters_absolute_tolerance,
        initial_concentrations_relative_tolerance=initial_concentrations_relative_tolerance, initial_concentrations_absolute_tolerance=initial_concentrations_absolute_tolerance)

    # prepare measurement object
    measurements_object = simulation.model.save.prepare_measurements(
        model_options,
        min_measurements_standard_deviation=min_measurements_standard_deviations,
        min_measurements_correlation=min_measurements_correlations,
        min_standard_deviation=min_standard_deviations,
        correlation_decomposition_min_value_D=correlation_decomposition_min_value_D,
        max_box_distance_to_water=max_box_distance_to_water)

    # create accuracy object
    if cost_function_name == 'OLS':
        accuracy_class = simulation.accuracy.linearized.OLS
    elif cost_function_name == 'WLS':
        accuracy_class = simulation.accuracy.linearized.WLS
    elif cost_function_name == 'GLS':
        accuracy_class = simulation.accuracy.linearized.GLS
    else:
        raise ValueError(f'Unknown cost_function_name {cost_function_name}.')
    accuracy_object = accuracy_class(measurements_object, model_options=model_options)

    time_dim_confidence = 12
    accuracy_object.model_parameter_correlation_matrix()
    for include_variance_factor in (True, False):
        accuracy_object.model_parameter_covariance_matrix(include_variance_factor=include_variance_factor)
        accuracy_object.model_confidence(alpha=alpha, time_dim_confidence=time_dim_confidence, time_dim_model=time_dim_model, include_variance_factor=include_variance_factor, parallel=parallel)
        for relative in (True, False):
            accuracy_object.model_parameter_confidence(alpha=alpha, relative=relative, include_variance_factor=include_variance_factor)
            for per_tracer in (True, False):
                accuracy_object.average_model_confidence(alpha=alpha, time_dim_model=time_dim_model, per_tracer=per_tracer, include_variance_factor=include_variance_factor, relative=relative, parallel=parallel)
    accuracy_object.average_model_confidence_increase(alpha=alpha, time_dim_confidence_increase=time_dim_confidence, time_dim_model=time_dim_model, relative=True, include_variance_factor=True, parallel=parallel, number_of_measurements=1)


# *** main function for script call *** #

def _main():

    # parse arguments
    import argparse

    parser = argparse.ArgumentParser(description='Evaluate and save model accuracy.')

    parser.add_argument('cost_function_name', choices=('OLS', 'WLS', 'GLS'), default=None, help='The cost functions to evaluate.')

    parser.add_argument('model_name', choices=simulation.model.constants.MODEL_NAMES, help='The name of the model that should be used.')
    parser.add_argument('--time_step', type=int, default=1, help='The time step of the model that should be used. Default: 1')

    parser.add_argument('--concentrations', type=float, nargs='+', help='The constant concentration values for the tracers in the initial spinup that should be used. If not specified the default model concentrations are used.')
    parser.add_argument('--concentrations_index', type=int, help='The constant concentration index that should be used if no constant concentration values are specified.')

    parser.add_argument('--parameters', type=float, nargs='+', help='The model parameters that should be used.')
    parser.add_argument('--parameter_set_index', type=int, help='The model parameter index that should be used if no model parameters are specified.')

    parser.add_argument('--spinup_years', type=int, default=10000, help='The number of years for the spinup.')
    parser.add_argument('--spinup_tolerance', type=float, default=0, help='The tolerance for the spinup.')
    parser.add_argument('--spinup_satisfy_years_and_tolerance', action='store_true', help='If used, the spinup is terminated if years and tolerance have been satisfied. Otherwise, the spinup is terminated as soon as years or tolerance have been satisfied.')

    parser.add_argument('--derivative_step_size', type=float, default=None, help='The step size used for the finite difference approximation.')
    parser.add_argument('--derivative_years', type=int, default=None, help='The number of years for the finite difference approximation spinup.')
    parser.add_argument('--derivative_accuracy_order', type=int, default=None, help='The accuracy order used for the finite difference approximation. 1 = forward differences. 2 = central differences.')

    parser.add_argument('--min_measurements_standard_deviations', nargs='+', type=int, default=None, help='The minimal number of measurements used to calculate standard deviations applied to each dataset.')
    parser.add_argument('--min_standard_deviations', nargs='+', type=float, default=None, help='The minimal standard deviations assumed for the measurement errors applied to each dataset.')
    parser.add_argument('--min_measurements_correlations', nargs='+', type=int, default=None, help='The minimal number of measurements used to calculate correlations applied to each dataset.')
    parser.add_argument('--correlation_decomposition_min_value_D', type=float, default=None, help='The minimal value aplied to the diagonal of the decomposition of the correlation matrix applied to each dataset.')
    parser.add_argument('--max_box_distance_to_water', type=int, default=float('inf'), help='The maximal distance to water boxes to accept measurements.')

    parser.add_argument('--model_parameters_relative_tolerance', type=float, nargs='+', default=10**-6, help='The relative tolerance up to which two model parameter vectors are considered equal.')
    parser.add_argument('--model_parameters_absolute_tolerance', type=float, nargs='+', default=10**-6, help='The absolute tolerance up to which two model parameter vectors are considered equal.')

    parser.add_argument('--initial_concentrations_relative_tolerance', type=float, default=10**-6, help='The relative tolerance up to which two initial concentration vectors are considered equal.')
    parser.add_argument('--initial_concentrations_absolute_tolerance', type=float, default=10**-6, help='The absolute tolerance up to which two initial concentration vectors are considered equal.')

    parser.add_argument('--alpha', type=float, default=0.99, help='The confidence level.')
    parser.add_argument('--time_dim_model', type=int, default=None, help='Used time dim of model.')
    parser.add_argument('--parallel', action='store_true', help='Run in parallel.')

    parser.add_argument('-d', '--debug', action='store_true', help='Print debug infos.')

    parser.add_argument('--version', action='version', version='%(prog)s {}'.format(simulation.__version__))

    args = parser.parse_args()

    if args.concentrations is None and args.concentrations_index is None:
        raise ValueError('"--concentrations" or "--concentrations_index" must be specified. Use "--help" for more infos.')
    if args.parameters is None and args.parameter_set_index is None:
        raise ValueError('"--concentrations" or "--concentrations_index" must be specified. Use "--help" for more infos.')

    # call function
    with util.logging.Logger(disp_stdout=args.debug):
        save(args.cost_function_name,
             args.model_name,
             time_step=args.time_step,
             spinup_years=args.spinup_years,
             spinup_tolerance=args.spinup_tolerance,
             spinup_satisfy_years_and_tolerance=args.spinup_satisfy_years_and_tolerance,
             concentrations=args.concentrations,
             concentrations_index=args.concentrations_index,
             parameters=args.parameters,
             parameter_set_index=args.parameter_set_index,
             derivative_years=args.derivative_years,
             derivative_step_size=args.derivative_step_size,
             derivative_accuracy_order=args.derivative_accuracy_order,
             model_parameters_relative_tolerance=args.model_parameters_relative_tolerance,
             model_parameters_absolute_tolerance=args.model_parameters_absolute_tolerance,
             initial_concentrations_relative_tolerance=args.initial_concentrations_relative_tolerance,
             initial_concentrations_absolute_tolerance=args.initial_concentrations_absolute_tolerance,
             min_measurements_standard_deviations=args.min_measurements_standard_deviations,
             min_standard_deviations=args.min_standard_deviations,
             min_measurements_correlations=args.min_measurements_correlations,
             correlation_decomposition_min_value_D=args.correlation_decomposition_min_value_D,
             max_box_distance_to_water=args.max_box_distance_to_water,
             alpha=args.alpha,
             time_dim_model=args.time_dim_model,
             parallel=args.parallel)
        util.logging.info('Finished.')


if __name__ == "__main__":
    _main()
