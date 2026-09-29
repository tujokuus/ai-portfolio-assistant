# Local AI Lecture and Meeting Assistant

## Summary

Local Voice Agent is Tuomas Kuusisto's individual, learning-focused Python application for processing English audio recordings. The README describes local transcription, structured summaries, and evidence-based question answering over a stored session. Tuomas confirms that he built the project individually and that it is not finished.

## Background and timing

The repository README does not state when the project began. It describes an English-only MVP and lists capabilities already available alongside features excluded from the initial scope.

## Tuomas's contribution

Tuomas says he completed the project individually. The repository describes a local audio-processing pipeline, persistence, summarization, transcript retrieval, and a manually implemented agent workflow. The current README does not attribute work to other contributors.

## Technologies and their uses

- Python for the application and command-line interface.
- `faster-whisper` for local English audio transcription.
- Ollama for local-model summarization and question-answering requests.
- SQLite for session data, timestamped transcript segments, summaries, and evaluation history.
- Pydantic for validating structured outputs.
- A versioned JSON dataset and deterministic evaluation runner for transcript question-answering comparisons.

## Technical approach

The documented pipeline transcribes English audio into timestamped segments, groups them into approximately ten-minute sentence-aware chunks, and uses a local Ollama model to generate checkpoint notes and an overall summary. Transcript data and outputs are stored in SQLite. A bounded agent workflow uses read-only transcript-search, transcript-range, and stored-summary tools. The application validates segment identifiers and renders timestamp citations from retrieved transcript evidence.

The README describes deterministic evaluation metrics for execution success, answerability decisions, retrieval evidence recall, citation recall and precision, and processing time. It explicitly cautions that evidence-overlap scores do not establish that a natural-language answer is correct or fully supported.

## Results and current status

The README says that transcription, hierarchical summarization, transcript search and range retrieval, and an initial read-only question-answering workflow are available. It documents test use of a Whisper fixture, an earlier summary check on a 15-minute English spoken article, and a versioned 12-case question-answering dataset. These are described as development checks and evaluation facilities, not as production outcomes or proof of general answer accuracy.

Speaker diarization, real-time recording, graphical interfaces, mobile clients, embeddings, and cross-session retrieval are outside the stated initial scope. The user confirms that the overall project is unfinished.

## Sources

- [GitHub repository and README](https://github.com/tujokuus/local-voice-agent)
- [Portfolio page](https://tujokuus.github.io/)
