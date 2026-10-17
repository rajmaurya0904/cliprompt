"""Tests for CLI output formatting."""

from cliprompt.cli import main


def test_cli_output(capsys):
    """Test that the CLI prints the expected output."""
    # Call main with empty argv (simulating no arguments)
    main(argv=[])
    captured = capsys.readouterr()
    expected_out = (
        "Cliprompt command-line interface\n"
        "This is a placeholder for the actual CLI implementation.\n"
    )
    assert captured.out == expected_out
    assert captured.err == ""
    # The main function returns 0, but we don't need to check that here.


def test_cli_output_with_argv(capsys):
    """Test that the CLI ignores arguments (for now) and still prints the same output."""
    main(argv=["--help"])
    captured = capsys.readouterr()
    expected_out = (
        "Cliprompt command-line interface\n"
        "This is a placeholder for the actual CLI implementation.\n"
    )
    assert captured.out == expected_out
    assert captured.err == ""