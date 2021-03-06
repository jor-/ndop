import simulation
import simulation.optimization.cost_function
import simulation.optimization.job
import simulation.model.constants
import simulation.model.options
import simulation.util.args

import measurements.all.data

import util.batch.universal.system
import util.logging


def save(cost_functions, model_names=None, eval_f=True, eval_df=False, eval_d2f=False):
    for cost_function in simulation.optimization.cost_function.iterator(cost_functions, model_names=model_names, skip_os_errors=True):
        try:
            eval_f_for_cf = eval_f and not cost_function.f_available()
            eval_df_for_cf = eval_df and not cost_function.df_available(derivative_order=1)
            eval_d2f_for_cf = eval_d2f and not cost_function.df_available(derivative_order=2)
            util.logging.debug(f'Saving cost function values {cost_function.name} in {cost_function.model.parameter_set_dir} for eval_f {eval_f_for_cf} and eval_df {eval_df_for_cf} and eval_d2f {eval_d2f_for_cf} are already available.')
            if eval_f_for_cf or eval_df_for_cf or eval_d2f_for_cf:
                if eval_f_for_cf:
                    cost_function.f()
                if eval_df_for_cf:
                    cost_function.df(derivative_order=1)
                if eval_d2f_for_cf:
                    cost_function.df(derivative_order=2)
            else:
                util.logging.debug(f'Cost function values {cost_function.name} in {cost_function.model.parameter_set_dir} with eval_f {eval_f} and eval_df {eval_df} and eval_d2f {eval_d2f} are already available.')
        except Exception:
            util.logging.error('Cost function could not be evaluated.', exc_info=True)


def save_for_all_measurements_serial(cost_function_names=None, model_names=None, min_measurements_standard_deviations=None, min_measurements_correlations=None, min_standard_deviations=None, correlation_decomposition_min_value_D=None, correlation_decomposition_min_abs_value_L=None, max_box_distance_to_water=None, eval_f=True, eval_df=False, eval_d2f=False):
    # get cost_function_classes
    if cost_function_names is None:
        cost_function_classes = None
    else:
        cost_function_classes = [getattr(simulation.optimization.cost_function, cost_function_name) for cost_function_name in cost_function_names]
    # init cost functions
    model_options = simulation.model.options.ModelOptions()
    model_options.spinup_options = {'years': 1, 'tolerance': 0.0, 'combination': 'or'}
    cost_functions = simulation.optimization.cost_function.cost_functions_for_all_measurements(
        min_measurements_standard_deviations=min_measurements_standard_deviations,
        min_measurements_correlations=min_measurements_correlations,
        min_standard_deviations=min_standard_deviations,
        correlation_decomposition_min_value_D=correlation_decomposition_min_value_D,
        correlation_decomposition_min_abs_value_L=correlation_decomposition_min_abs_value_L,
        max_box_distance_to_water=max_box_distance_to_water,
        cost_function_classes=cost_function_classes,
        model_options=model_options)
    if eval_df or eval_d2f:
        for cost_function in cost_functions:
            cost_function.include_initial_concentrations_factor_to_model_parameters = True
    # save values
    save(cost_functions, model_names=model_names, eval_f=eval_f, eval_df=eval_df, eval_d2f=eval_d2f)


def save_for_all_measurements_as_jobs(cost_function_names=None, model_names=None, min_measurements_standard_deviations=None, min_measurements_correlations=None, min_standard_deviations=None, correlation_decomposition_min_value_D=None, correlation_decomposition_min_abs_value_L=None, max_box_distance_to_water=None, eval_f=True, eval_df=False, eval_d2f=False, node_kind=None, max_parallel_jobs=100):
    if eval_f or eval_df or eval_d2f:
        # prepare
        model_job_options = None
        include_initial_concentrations_factor_to_model_parameters = True

        nodes_setup = simulation.optimization.constants.NODES_SETUP_JOB.copy()
        if node_kind is not None:
            nodes_setup.node_kind = node_kind
            nodes_setup.check_for_better = False
        cost_function_job_options = {'nodes_setup': nodes_setup}

        if cost_function_names is None:
            cost_function_names = simulation.optimization.cost_function.ALL_COST_FUNCTION_NAMES

        running_jobs = []

        def wait_for_next_job():
            with running_jobs.pop(0) as cf_job:
                # print waiting info
                try:
                    is_finished = cf_job.is_finished(check_exit_code=False)
                except util.batch.universal.system.job.JobError:
                    is_finished = True
                if not is_finished:
                    util.logging.info(f'Waiting for cost function evaluation {cf_job} to finish.')
                # wait for finishing and remove
                try:
                    cf_job.wait_until_finished(check_exit_code=True)
                except util.batch.universal.system.JobError as error:
                    util.logging.error(f'Cost function evaluation {cf_job} failed due to {error}.')
                else:
                    try:
                        cf_job.remove()
                    except OSError as error:
                        util.logging.warn(f'Cost function evaluation {cf_job} could not be removed due to {error}.')

        # evaluate
        for cost_function_name in cost_function_names:
            cost_function_class = getattr(simulation.optimization.cost_function, cost_function_name)

            for model_name in model_names:
                model = simulation.model.cache.Model(job_options=model_job_options)

                for model_options in model.iterator(model_names=[model_name]):
                    # init cost function object
                    measurements_object = simulation.util.args.init_measurements(
                        model_options,
                        min_measurements_standard_deviation=min_measurements_standard_deviations,
                        min_measurements_correlation=min_measurements_correlations,
                        min_standard_deviation=min_standard_deviations,
                        correlation_decomposition_min_value_D=correlation_decomposition_min_value_D,
                        correlation_decomposition_min_abs_value_L=correlation_decomposition_min_abs_value_L,
                        max_box_distance_to_water=max_box_distance_to_water)
                    cost_function = cost_function_class(
                        measurements_object,
                        model_options=model_options,
                        model_job_options=model_job_options,
                        include_initial_concentrations_factor_to_model_parameters=include_initial_concentrations_factor_to_model_parameters)

                    try:
                        # check if evaluation is needed
                        eval_f_for_cf = eval_f and not cost_function.f_available()
                        eval_df_for_cf = eval_df and not cost_function.df_available(derivative_order=1)
                        eval_d2f_for_cf = eval_d2f and not cost_function.df_available(derivative_order=2)

                        # wait for running jobs to finish
                        if (eval_f_for_cf or eval_df_for_cf or eval_d2f_for_cf) and max_parallel_jobs is not None and len(running_jobs) > max_parallel_jobs:
                            wait_for_next_job()
                    except util.batch.universal.system.JobError as error:
                        util.logging.error(f'Cost function evaluation {cf_job} failed due to {error}.')
                    else:
                        # start job if needed
                        if eval_f_for_cf or eval_df_for_cf:
                            with simulation.optimization.job.CostFunctionJob(
                                    cost_function_name,
                                    model_options,
                                    model_job_options=model_job_options,
                                    min_measurements_standard_deviations=min_measurements_standard_deviations,
                                    min_measurements_correlations=min_measurements_correlations,
                                    min_standard_deviations=min_standard_deviations,
                                    correlation_decomposition_min_value_D=correlation_decomposition_min_value_D,
                                    correlation_decomposition_min_abs_value_L=correlation_decomposition_min_abs_value_L,
                                    max_box_distance_to_water=max_box_distance_to_water,
                                    eval_f=eval_f_for_cf,
                                    eval_df=eval_df_for_cf,
                                    eval_d2f=eval_d2f_for_cf,
                                    cost_function_job_options=cost_function_job_options,
                                    include_initial_concentrations_factor_to_model_parameters=include_initial_concentrations_factor_to_model_parameters,
                                    remove_output_dir_on_close=False) as cf_job:
                                cf_job.start()

                                util.logging.info(f'Cost function {cost_function_name} for values in {model.parameter_set_dir} with eval_f={eval_f_for_cf} and eval_df={eval_df_for_cf} and eval_d2f={eval_d2f_for_cf} job started with id {cf_job.id}.')

                            running_jobs.append(cf_job)
                        else:
                            util.logging.debug(f'Cost function {cost_function_name} for values in {model.parameter_set_dir} with eval_f={eval_f_for_cf} and eval_df={eval_df_for_cf} and eval_d2f={eval_d2f_for_cf} are already available.')

        # remove all jobs
        while len(running_jobs) > 0:
            wait_for_next_job()


def save_for_all_measurements(cost_function_names=None, model_names=None, min_measurements_standard_deviations=None, min_measurements_correlations=None, min_standard_deviations=None, correlation_decomposition_min_value_D=None, correlation_decomposition_min_abs_value_L=None, max_box_distance_to_water=None, eval_f=True, eval_df=False, eval_d2f=False, node_kind=None, number_of_jobs=0):
    if number_of_jobs is None or number_of_jobs == 0:
        save_for_all_measurements_serial(
            cost_function_names=cost_function_names,
            model_names=model_names,
            min_measurements_standard_deviations=min_measurements_standard_deviations,
            min_measurements_correlations=min_measurements_correlations,
            min_standard_deviations=min_standard_deviations,
            correlation_decomposition_min_value_D=correlation_decomposition_min_value_D,
            correlation_decomposition_min_abs_value_L=correlation_decomposition_min_abs_value_L,
            max_box_distance_to_water=max_box_distance_to_water,
            eval_f=eval_f,
            eval_df=eval_df,
            eval_d2f=eval_d2f)
    else:
        save_for_all_measurements_as_jobs(
            cost_function_names=cost_function_names,
            model_names=model_names,
            min_measurements_standard_deviations=min_measurements_standard_deviations,
            min_measurements_correlations=min_measurements_correlations,
            min_standard_deviations=min_standard_deviations,
            correlation_decomposition_min_value_D=correlation_decomposition_min_value_D,
            correlation_decomposition_min_abs_value_L=correlation_decomposition_min_abs_value_L,
            max_box_distance_to_water=max_box_distance_to_water,
            eval_f=eval_f,
            eval_df=eval_df,
            eval_d2f=eval_d2f,
            node_kind=node_kind,
            max_parallel_jobs=number_of_jobs)


# *** main function for script call *** #

def _main():

    # parse arguments
    import argparse

    parser = argparse.ArgumentParser(description='Calculating cost function values.')
    simulation.util.args.argparse_add_measurement_options(parser)
    parser.add_argument('--cost_functions', type=str, default=None, nargs='+', help='The cost functions to evaluate.')
    parser.add_argument('--model_names', type=str, default=None, choices=simulation.model.constants.MODEL_NAMES, nargs='+', help='The models to evaluate.')
    parser.add_argument('--DF', action='store_true', help='Eval (also) DF.')
    parser.add_argument('--D2F', action='store_true', help='Eval (also) D2F.')
    parser.add_argument('--number_of_jobs', type=int, default=0, help='The number of parallel batch jobs used for calculations.')
    parser.add_argument('--node_kind', default=None, help='The kind of nodes to use for the batch jobs.')
    parser.add_argument('--debug_level', choices=util.logging.LEVELS, default='INFO', help='Print debug infos low to passed level.')
    parser.add_argument('--version', action='version', version='%(prog)s {}'.format(simulation.__version__))
    args = parser.parse_args()

    # run
    with util.logging.Logger(level=args.debug_level):
        save_for_all_measurements(
            cost_function_names=args.cost_functions,
            model_names=args.model_names,
            min_measurements_standard_deviations=args.min_measurements_standard_deviations,
            min_measurements_correlations=args.min_measurements_correlations,
            min_standard_deviations=args.min_standard_deviations,
            correlation_decomposition_min_value_D=args.correlation_decomposition_min_value_D,
            correlation_decomposition_min_abs_value_L=args.correlation_decomposition_min_abs_value_L,
            max_box_distance_to_water=args.max_box_distance_to_water,
            eval_f=True,
            eval_df=args.DF,
            eval_d2f=args.D2F,
            node_kind=args.node_kind,
            number_of_jobs=args.number_of_jobs)
        util.logging.info('Finished.')


if __name__ == "__main__":
    _main()
