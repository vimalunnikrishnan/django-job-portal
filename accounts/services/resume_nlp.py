import re


# Predefined skills library
SKILL_ALIASES = {
    "Python": [
        "Python",
    ],

    "Django": [
        "Django",
    ],

    "Django REST Framework": [
        "Django REST Framework",
        "DRF",
    ],

    "Flask": [
        "Flask",
    ],

    "JavaScript": [
        "JavaScript",
        "JS",
    ],

    "React": [
        "React",
        "React.js",
    ],

    "HTML": [
        "HTML",
        "HTML5",
    ],

    "CSS": [
        "CSS",
        "CSS3",
    ],

    "SQL": [
        "SQL",
    ],

    "MySQL": [
        "MySQL",
    ],

    "PostgreSQL": [
        "PostgreSQL",
        "Postgres",
    ],

    "MongoDB": [
        "MongoDB",
    ],

    "Git": [
        "Git",
    ],

    "GitHub": [
        "GitHub",
    ],

    "REST API": [
        "REST API",
        "REST APIs",
        "RESTful API",
        "RESTful APIs",
    ],

    "Machine Learning": [
        "Machine Learning",
        "ML",
    ],

    "Data Science": [
        "Data Science",
    ],
}


def tokenize_text(text):
    """
    Split resume text into individual words/tokens.
    """

    return re.findall(r"\b[\w+#.-]+\b", text)


def extract_keywords(text):
    """
    Extract meaningful keywords from resume text
    by removing common stop words.
    """

    stop_words = {
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "as",
        "at",
        "by",
        "from",
        "into",
        "through",
        "this",
        "that",
        "these",
        "those",
        "using",
        "used",
        "have",
        "has",
        "had",
        "been",
        "being",
        "can",
        "will",
        "would",
        "should",
        "their",
        "they",
        "them",
        "it",
        "its",
        "my",
        "our",
        "your",
        "we",
        "you",
        "I",
    }

    tokens = tokenize_text(text)

    keywords = []

    for token in tokens:

        normalized_token = token.lower()

        if (
            len(token) > 2
            and normalized_token not in stop_words
        ):
            keywords.append(token)

    return list(dict.fromkeys(keywords))


def extract_skills(text):
    """
    Match predefined skills and normalize aliases
    into canonical skill names.
    """

    skills = []

    for canonical_skill, aliases in SKILL_ALIASES.items():

        for alias in aliases:

            pattern = r"\b" + re.escape(alias) + r"\b"

            if re.search(pattern, text, re.IGNORECASE):
                skills.append(canonical_skill)
                break

    return skills


def extract_experience_years(text):
    """
    Extract years of experience from resume text.
    """

    patterns = [
        r"(\d+(?:\.\d+)?)\+?\s*years?\s+(?:of\s+)?experience",
        r"experience\s*[:\-]?\s*(\d+(?:\.\d+)?)\+?\s*years?",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            return float(match.group(1))

    return 0


def extract_roles(text):
    """
    Detect common job roles from resume text.
    """

    roles_library = [
        "Python Developer",
        "Django Developer",
        "Backend Developer",
        "Full Stack Developer",
        "Software Developer",
        "Software Engineer",
        "Web Developer",
        "Data Analyst",
        "Data Scientist",
        "Machine Learning Engineer",
    ]

    roles = []

    for role in roles_library:

        pattern = r"\b" + re.escape(role) + r"\b"

        if re.search(pattern, text, re.IGNORECASE):
            roles.append(role)

    return roles


EDUCATION_ALIASES = {
    "BCA": [
        "BCA",
        "Bachelor of Computer Applications",
    ],

    "MCA": [
        "MCA",
        "Master of Computer Applications",
    ],

    "B.Tech": [
        "B.Tech",
        "BTech",
        "Bachelor of Technology",
    ],

    "M.Tech": [
        "M.Tech",
        "MTech",
        "Master of Technology",
    ],

    "B.E": [
        "B.E",
        "BE",
        "Bachelor of Engineering",
    ],

    "M.E": [
        "M.E",
        "ME",
        "Master of Engineering",
    ],

    "B.Sc": [
        "B.Sc",
        "BSc",
        "Bachelor of Science",
    ],

    "M.Sc": [
        "M.Sc",
        "MSc",
        "Master of Science",
    ],

    "MBA": [
        "MBA",
        "Master of Business Administration",
    ],
}


def extract_education(text):
    """
    Detect education qualifications and normalize
    them into canonical qualification names.
    """

    education = []

    for qualification, aliases in EDUCATION_ALIASES.items():

        for alias in aliases:

            pattern = r"\b" + re.escape(alias) + r"\b"

            if re.search(pattern, text, re.IGNORECASE):
                education.append(qualification)
                break

    return education


def parse_resume(text):
    """
    Convert cleaned resume text into structured resume data.
    """

    return {
        "keywords": extract_keywords(text),
        "skills": extract_skills(text),
        "experience": {
            "years": extract_experience_years(text),
            "roles": extract_roles(text),
        },
        "education": extract_education(text),
    }