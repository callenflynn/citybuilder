use pyo3::prelude::*;
use pyo3::Python;
use pyo3::types::PyModule;
use pyo3::Bound;

/// Version of the Rust simulation core.
#[pyfunction]
fn sim_version() -> &'static str {
    "0.1.0-m0-rust"
}

/// Placeholder: one deterministic sim tick.
///
/// Every simulation system is written in Python first; this Rust stub is the
/// boundary that hot systems get ported into once profiling justifies it.
/// When the first system is ported, its state will be exposed as NumPy arrays
/// (ndarray + pyo3-numpy) so Python debug tools can inspect it.
#[pyfunction]
fn sim_tick(tick: u64) -> u64 {
    tick + 1
}

#[pymodule]
fn citybuilder_sim(_py: Python, module: Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(sim_version, &module)?)?;
    module.add_function(wrap_pyfunction!(sim_tick, &module)?)?;
    Ok(())
}
