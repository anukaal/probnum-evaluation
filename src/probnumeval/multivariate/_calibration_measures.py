"""Uncertainty calibration measures."""

from typing import Union

import numpy as np
import scipy.linalg
import scipy.stats
from probnum import _randomvariablelist, randvars

from probnumeval import config
from probnumeval.type import DeterministicSolutionType, ProbabilisticSolutionType

__all__ = [
    "anees",
    "nci",
]


def anees(
    approximate_solution: Union[
        randvars.Normal, _randomvariablelist._RandomVariableList
    ],
    reference_solution: np.ndarray,
):
    r"""Compute the average normalised estimation error squared.

    Also known as chi-squared statistic. It computes

    .. math:: \chi^2 :=
        \frac{1}{N + 1}
        \sum_{n=0}^N
        (y^*(t_n) - \mathbb{E}[y(t_n)])^\top
        \mathbb{C}[y(t_n)]^{-1}
        (y^*(t_n) - \mathbb{E}[y(t_n)])

    where :math:`\mathbb{E}` is the mean and :math:`\mathbb{C}` is the covariance.
    If :math:`y` is a Gaussian process, :math:`\chi^2` follows a chi-squared distribution.
    For a :math:`d` dimensional solution, the outcome is

    - **Underconfident** if :math:`\chi^2 < d` holds. The estimated error is way larger than the actual error.
    - **Overconfident** if :math:`\chi^2 > d` holds. The estimated error is way smaller than the actual error.

    Parameters
    ----------
    approximate_solution :
        Approximate solution as returned by a (Gaussian) probabilistic numerical method.
    reference_solution :
        Reference solution. This is an array, because it must be a deterministic point-estimate.

    Returns
    -------
    ANEES statistic (i.e. :math:`\chi^2` above).

    See also
    --------
    chi2_confidence_intervals
        Confidence intervals for the ANEES test statistic.
    nci
        An alternative calibration measure.

    """
    cov_matrices = approximate_solution.cov
    centered_mean = approximate_solution.mean - reference_solution
    normalized_discrepancies = _compute_normalized_discrepancies(
        centered_mean, cov_matrices
    )
    return np.mean(normalized_discrepancies)


def nci(
    approximate_solution: Union[
        randvars.Normal, _randomvariablelist._RandomVariableList
    ],
    reference_solution: np.ndarray,
):
    r"""Compute the non-credibility index (NCI).

    The NCI indicates whether an estimate is

    - **Underconfident** if :math:`\text{NCI} < 0` holds. The estimated error is way larger than the actual error.
    - **Overconfident** if :math:`\text{NCI} > 0` holds. The estimated error is way smaller than the actual error.

    Parameters
    ----------
    approximate_solution :
        Approximate solution as returned by a (Gaussian) probabilistic numerical method.
    reference_solution :
        Reference solution. This is an array, because it must be a deterministic point-estimate.

    Returns
    -------
    NCI statistic.

    See also
    --------
    anees
        An alternative calibration measure.

    """
    cov_matrices = approximate_solution.cov
    centered_mean = approximate_solution.mean - reference_solution
    normalized_discrepancies = _compute_normalized_discrepancies(
        centered_mean, cov_matrices
    )

    sample_covariance_matrix = np.tile(
        np.cov(centered_mean.T), reps=(len(centered_mean), 1, 1)
    )
    reference_discrepancies = _compute_normalized_discrepancies(
        centered_mean, sample_covariance_matrix
    )
    nci = 10 * (
        np.mean(np.log10(normalized_discrepancies))
        - np.mean(np.log10(reference_discrepancies))
    )
    return nci


def _compute_components(approximate_solution, locations, reference_solution):
    approximate_evaluation = approximate_solution(locations)
    reference_evaluation = reference_solution(locations)
    cov_matrices = approximate_evaluation.cov
    centered_mean = approximate_evaluation.mean - reference_evaluation
    return centered_mean, cov_matrices


def _compute_normalized_discrepancies(centered_mean, cov_matrices):
    return np.array(
        [
            _compute_normalized_discrepancy(m, C)
            for (m, C) in zip(centered_mean, cov_matrices)
        ]
    )


def _compute_normalized_discrepancy(mean, cov):

    if config.COVARIANCE_INVERSION["symmetrize"]:
        cov = 0.5 * (cov + cov.T)
    if config.COVARIANCE_INVERSION["damping"] > 0.0:
        cov += config.COVARIANCE_INVERSION["damping"] * np.eye(len(cov))

    if config.COVARIANCE_INVERSION["strategy"] == "inv":
        return mean @ np.linalg.inv(cov) @ mean
    if config.COVARIANCE_INVERSION["strategy"] == "pinv":
        return mean @ np.linalg.pinv(cov) @ mean
    if config.COVARIANCE_INVERSION["strategy"] == "solve":
        return mean @ np.linalg.solve(cov, mean)
    if config.COVARIANCE_INVERSION["strategy"] == "cholesky":
        L, lower = scipy.linalg.cho_factor(cov, lower=True)
        return mean @ scipy.linalg.cho_solve((L, lower), mean)

    raise ValueError("Covariance inversion parameters are not known.")
