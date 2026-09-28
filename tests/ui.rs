#[test]
fn constitutional_type_boundary() {
    let t = trybuild::TestCases::new();
    t.compile_fail("tests/ui/*.rs");
}
