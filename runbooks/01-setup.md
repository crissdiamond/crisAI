# crisAI setup

1. Unzip the pack.
2. Run `bash ./scripts/bootstrap.sh`.
3. Edit `.env` and set `OPENAI_API_KEY`.
4. Activate the virtual environment.
5. Export `PYTHONPATH=./src`.
6. Run `python -m crisai.cli.main list-servers`.
7. Run `python -m crisai.cli.main list-agents`.
8. Test with `python -m crisai.cli.main ask --pipeline --verbose -m "List the files in the workspace."`.
