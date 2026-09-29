# Source review checklist — not portfolio data

This file records source limitations and questions for Tuomas. It is outside `data/` and must not be ingested as verified portfolio content.

## Sources actually read

- `resume.pdf`: extracted text from both pages and visually inspected both rendered pages.
- [Portfolio page](https://tujokuus.github.io/): read the page content, including its profile, experience, and project descriptions.
- [Air Strikes on Ukraine Analysis Dashboard repository README](https://github.com/tujokuus/air-strikes-on-ukraine-dashboard): read the rendered README. No additional source files were read.
- [Car Price Prediction repository README](https://github.com/tujokuus/car-prize-prediction): read the rendered README. No notebooks or source files were read.
- [Local Voice Agent repository README](https://github.com/tujokuus/local-voice-agent): read the rendered README. No additional source files were read.

## Missing information and conflicts

1. **Cense Analytics job title:** The CV calls the autumn 2025 role “Machine Learning & Data Science Intern.” The portfolio heading calls it “Junior Data Scientist,” while its profile text calls the current role an internship. Which exact title should the experience document use?
2. **Cense Analytics dates:** The CV says “2025 autumn” with an arrow and the portfolio says the internship is current. What are the exact start month/year and, if applicable, end date? Does the summer employee period directly precede the internship?
3. **Car-price results:** The portfolio reports model metrics on a held-out test set, while the repository README warns that the current validation split was used during model exploration and asks for a new untouched test set before final performance is reported. Are the portfolio figures from a separate, untouched test set? If so, which figures and evaluation setup are final and suitable for publication?
4. **Local Voice Agent model and agent implementation:** The portfolio mentions local Qwen models and a PydanticAI implementation. The current repository README documents Ollama and a manually implemented agent workflow but does not mention PydanticAI. Is PydanticAI implemented in the current repository, and which model names have actually been used in completed evaluations?
5. **Local Voice Agent evaluation claim:** The portfolio reports a word error rate comparison using an approximately 50-minute MIT OpenCourseWare lecture. The README read here documents other checks but not that comparison. Is the comparison documented in another public source, and may its test conditions and result be described?
6. **Education status:** The CV says the programme is present; the portfolio says Tuomas is finishing a bachelor's degree and pursuing a master's degree. What is the bachelor's completion status/date and the master's study status?
7. **Course-project scope:** The CV says the study-time tracking application was hosted on GitLab but provides no URL. What is the URL, which language did Tuomas use, and was the work individual or group work?
8. **Marathon database coursework:** Was the database coursework individual or group work? No date or database engine is provided in the CV.
9. **Thesis:** The CV and portfolio page read here provide no thesis title, topic, status, methods, supervisor, or results. Has Tuomas started or completed a thesis, and what source should document it?
10. **Other portfolio projects:** The portfolio also lists irrigation prediction, a giveaway agent, and a Korisliiga pick'em app, which were not among the requested repositories. Should any of these be added to the source documents?
11. **Project dates:** The three requested project README files do not state their start dates. If dates are important, provide the relevant start/end dates.

No assumptions have been used to resolve these items. Missing details are not evidence that the experience or skills are absent.
