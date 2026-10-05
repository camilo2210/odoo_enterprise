export class FrequencyViewerLocalConfig {
    constructor() {
        this.oldFreqKey = "aw_timesheet_frequency";
        this.freqKey = "aw_timesheet_suggestion_project_matching";
        this.matches = this.loadMatching();
        this.migrate();
        void this.scores;
        this.saveMatching(this.matches);
    }

    migrate() {
        const oldFreqStr = localStorage.getItem(this.oldFreqKey);
        if (oldFreqStr) {
            const oldFreq = JSON.parse(oldFreqStr);
            const now = new Date().toISOString();

            for (const [suggestion, dataMap] of Object.entries(oldFreq)) {
                for (const [jsonParams, count] of Object.entries(dataMap)) {
                    const data = JSON.parse(jsonParams);
                    for (let i = 0; i < count; i++) {
                        this.matches.push({
                            suggestion,
                            data,
                            datetime: now,
                        });
                    }
                }
            }
            this.saveMatching(this.matches);
            localStorage.removeItem(this.oldFreqKey);
        }
    }

    loadMatching() {
        return JSON.parse(localStorage.getItem(this.freqKey) || "[]");
    }

    saveMatching(matches) {
        localStorage.setItem(this.freqKey, JSON.stringify(matches));
    }

    addMatching(suggestion, data) {
        this.matches.push({
            suggestion,
            data,
            datetime: new Date().toISOString(),
        });

        const normalizedSuggestion = (suggestion || "").trim().toLowerCase();

        if (!this.scores[normalizedSuggestion]) {
            this.scores[normalizedSuggestion] = {};
        }

        const key = JSON.stringify(data);
        this.scores[normalizedSuggestion][key] = (this.scores[normalizedSuggestion][key] || 0) + 1;

        this.saveMatching(this.matches);
    }

    get scores() {
        if (this._scores) {
            return this._scores;
        }
        const computedScores = {};
        const now = new Date();
        const HALF_LIFE_DAYS = 7;
        const MS_PER_DAY = 1000 * 60 * 60 * 24;
        const CUTOFF_DAYS = 30;
        const suggestionGroups = {};
        for (const match of this.matches) {
            const normalizedSuggestion = (match.suggestion || "").trim().toLowerCase();
            if (!suggestionGroups[normalizedSuggestion]) {
                suggestionGroups[normalizedSuggestion] = [];
            }
            suggestionGroups[normalizedSuggestion].push(match);
        }
        const recentMatches = [];
        for (const [normSuggestion, group] of Object.entries(suggestionGroups)) {
            group.sort((a, b) => new Date(b.datetime) - new Date(a.datetime));
            computedScores[normSuggestion] = {};
            for (let index = 0; index < group.length; index++) {
                const match = group[index];
                const daysOld = Math.max(0, (now - new Date(match.datetime)) / MS_PER_DAY);
                if (daysOld <= CUTOFF_DAYS || index === 0) {
                    recentMatches.push(match);
                    const weight = Math.pow(0.5, daysOld / HALF_LIFE_DAYS);
                    const key = JSON.stringify(match.data);
                    computedScores[normSuggestion][key] =
                        (computedScores[normSuggestion][key] || 0) + weight;
                } else {
                    break;
                }
            }
        }
        recentMatches.sort((a, b) => new Date(a.datetime) - new Date(b.datetime));
        this.matches = recentMatches;
        this._scores = computedScores;
        return computedScores;
    }

    getDominantSuggestion(name) {
        if (!name) {
            return false;
        }
        const normalizedSuggestion = name.trim().toLowerCase();
        const suggestionScores = this.scores[normalizedSuggestion];
        if (!suggestionScores) {
            return false;
        }

        const entries = Object.entries(suggestionScores).map(([jsonKey, score]) => ({
            ...JSON.parse(jsonKey),
            score,
        }));

        const totalScore = entries.reduce((acc, e) => acc + e.score, 0);
        // 1. Check for dominant overall config
        entries.sort((a, b) => b.score - a.score);
        if (entries.length > 0 && entries[0].score * 2 > totalScore) {
            return entries[0];
        }

        // 2. No dominant overall config, check for dominant project
        const projectScores = entries.reduce((acc, entry) => {
            if (entry.project_id) {
                acc[entry.project_id] = (acc[entry.project_id] || 0) + entry.score;
            }
            return acc;
        }, {});

        const sortedProjects = Object.entries(projectScores).sort((a, b) => b[1] - a[1]);
        if (sortedProjects.length > 0) {
            const [bestProjectIdStr, bestProjectScore] = sortedProjects[0];
            const bestProjectId = parseInt(bestProjectIdStr);
            if (bestProjectScore * 2 > totalScore) {
                // Dominant project found, check for dominant task within it
                const taskScores = entries.reduce((acc, entry) => {
                    if (entry.project_id === bestProjectId && entry.task_id) {
                        acc[entry.task_id] = (acc[entry.task_id] || 0) + entry.score;
                    }
                    return acc;
                }, {});

                const sortedTasks = Object.entries(taskScores).sort((a, b) => b[1] - a[1]);
                if (sortedTasks.length > 0) {
                    const [bestTaskIdStr, bestTaskScore] = sortedTasks[0];
                    if (bestTaskScore * 2 > bestProjectScore) {
                        return { project_id: bestProjectId, task_id: parseInt(bestTaskIdStr) };
                    }
                }
                return { project_id: bestProjectId };
            }
        }

        return false;
    }
}
