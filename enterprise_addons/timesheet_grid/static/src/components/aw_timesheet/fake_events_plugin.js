import { Plugin, usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";
import { services } from "@web/core/services";

const { DateTime } = luxon;

function randomDuration(min = 600, max = 1800) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomChoice(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
}

const gdocTitles = [
    "Roadmap Q1",
    "Tech Debt Cleanup",
    "Meeting Notes",
    "Incident Postmortem",
    "Design Spec Draft",
    "Architecture Proposal",
    "Release Plan",
    "User Feedback Summary",
    "Sprint Retrospective",
];

const discordContacts = [
    "Marc Demo",
    "Joel Willis",
    "Julian Pine",
    "Clara Larkspur",
    "Ethan Brightwood",
    "Fiona Vale",
    "Marcus Goldwyn",
    "Lydia Quill",
    "Sebastian Brook",
    "Cecilia Dawn",
];

export class FakeEventsPlugin extends Plugin {
    orm = usePlugin(ORM);
    cache = {};
    odooUrl = window.location.origin;

    async _loadPartners() {
        const partners = await this.orm.searchRead(
            "res.partner",
            ["|", ["task_ids", "!=", false], ["project_ids", "!=", false], ["email", "!=", false]],
            ["email"],
            { limit: 10 }
        );

        return partners;
    }

    async _loadProjectsAndTasks() {
        const projects = await this.orm.searchRead(
            "project.project",
            [["is_template", "=", false]],
            ["id"]
        );
        const tasks = await this.orm.searchRead(
            "project.task",
            [["is_template", "=", false]],
            ["project_id"]
        );

        const tasksByProject = {};
        tasks.forEach((t) => {
            const pid = t.project_id[0];
            if (!tasksByProject[pid]) {
                tasksByProject[pid] = [];
            }
            tasksByProject[pid].push(t.id);
        });

        return { projects, tasksByProject };
    }

    async _generateEventsForDay(day) {
        const { projects, tasksByProject } = await this._loadProjectsAndTasks();
        const partners = await this._loadPartners();

        const start = new Date(`${day}T09:00:00`).getTime();
        const end = new Date(`${day}T17:00:00`).getTime();
        let cursor = start;

        const awWindow = [];
        const awBrowser = [];

        const browserPatterns = [
            () => ({
                title: `Lorem Ipsum · Pull Request #${Math.floor(Math.random() * 500)} · cool-repo`,
                url: `https://github.com/company/cool-repo/pull/${Math.floor(Math.random() * 500)}`,
            }),
            () => ({
                title: `${randomChoice(gdocTitles)} - Google Docs`,
                url: `https://docs.google.com/document/d/${Math.random().toString(36).slice(2)}`,
                type: "document",
            }),
        ];

        const gmailPatterns = [
            (partnerEmail) => ({
                data: {
                    gmail_activity: "composing_email",
                    subject: "Invitation to join Odoo Experience 2026",
                    to: [partnerEmail],
                },
            }),
            (partnerEmail) => ({
                data: {
                    gmail_activity: "reading_email",
                    subject: "Security alert",
                    from: partnerEmail,
                },
            }),
        ];

        const windowApps = [
            {
                app: "Discord",
                title: `@${randomChoice(discordContacts)} - Discord`,
                type: "messaging",
            },
            { app: "Terminal", title: "Terminal", type: "development" },
        ];

        while (cursor < end) {
            const duration = randomDuration();
            const stop = Math.min(cursor + duration * 1000, end);
            const r = Math.random();

            const eventData = (data, url = null, type = "development") => {
                const ev = {
                    timestamp: new Date(cursor).toISOString(),
                    duration: Math.floor((stop - cursor) / 1000),
                    start: DateTime.fromMillis(cursor),
                    stop: DateTime.fromMillis(stop),
                    type,
                    data,
                };
                if (url) {
                    ev.data.url = url;
                }
                return ev;
            };

            if (r < 0.1) {
                const proj = randomChoice(projects);
                const pid = proj.id;
                const tlist = tasksByProject[pid];
                const tid = tlist?.length ? randomChoice(tlist) : null;

                const url = tid
                    ? `${this.odooUrl}/odoo/project/${pid}/tasks/${tid}`
                    : `${this.odooUrl}/odoo/project/${pid}`;

                const title = tid ? `Project ${pid} - Task ${tid}` : `Project ${pid}`;

                awBrowser.push(eventData({ title, app: "Chrome" }, url, "odoo"));
            } else if (r < 0.3) {
                const gen = randomChoice(browserPatterns)();
                awBrowser.push(eventData({ title: gen.title, app: "Chrome" }, gen.url, gen.type));
            } else if (r < 0.8 && partners.length > 0) {
                const partnerEmail = randomChoice(partners).email;
                const mail = randomChoice(gmailPatterns)(partnerEmail);
                awBrowser.push(
                    eventData(
                        mail.data,
                        "https://mail.google.com/mail/u/0/#inbox",
                        "gmail_activity"
                    )
                );
            } else {
                const app = randomChoice(windowApps);
                awWindow.push(eventData({ title: app.title, app: app.app }, null, app.type));
            }

            cursor = stop;
        }

        return {
            fakeEvents: {
                currentwindow: awWindow,
                "web.tab.current": awBrowser,
            },
            partnerEmails: new Set(partners.map((partner) => partner.email)),
        };
    }

    async generate(day) {
        const data = await this._generateEventsForDay(day);
        this.cache[day] = data;
        return data;
    }

    get(day) {
        return (
            this.cache[day] || {
                fakeEvents: {
                    currentwindow: [],
                    "web.tab.current": [],
                },
                partnerEmails: new Set(),
            }
        );
    }

    clear(day) {
        delete this.cache[day];
    }
}

services.add(FakeEventsPlugin);
