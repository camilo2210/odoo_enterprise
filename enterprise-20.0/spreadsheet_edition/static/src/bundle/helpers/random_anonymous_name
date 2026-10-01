// Names are intentionally English-only and not wrapped in _t(). Adjective/noun
// agreement (gender, number) and adjective placement vary across languages
// (e.g. "Blue Whale" → "Baleine bleue" but "Blue Dog" → "Chien bleu"), so
// interpolating two word lists cannot produce grammatical output everywhere.
// Keeping the names in English — as other well known apps with a similar
// feature do — sidesteps the whole problem.
const THEMES = [
    // Friendly: adjective + small animal
    {
        parts: [
            // prettier-ignore
            [
                "Happy", "Clever", "Sleepy", "Jolly", "Brave", "Curious", "Gentle",
                "Witty", "Cheerful", "Lively", "Eager", "Bold", "Swift", "Quiet",
                "Playful", "Friendly", "Kind", "Merry", "Nimble", "Peaceful",
                "Silly", "Bouncy", "Graceful", "Wise", "Lucky", "Cozy", "Fluffy",
                "Sunny", "Dreamy", "Snug",
            ],
            // prettier-ignore
            [
                "Panda", "Fox", "Otter", "Koala", "Rabbit", "Penguin", "Squirrel",
                "Hedgehog", "Badger", "Beaver", "Owl", "Raccoon", "Chipmunk",
                "Lemur", "Meerkat", "Platypus", "Capybara", "Wombat", "Quokka",
                "Ferret", "Bunny", "Hamster", "Sloth", "Turtle", "Seal", "Dolphin",
                "Narwhal", "Puffin", "Swan", "Mole",
            ],
        ],
    },
    // Color + animal
    {
        parts: [
            // prettier-ignore
            [
                "Red", "Blue", "Green", "Yellow", "Purple", "Orange", "Pink",
                "Teal", "Crimson", "Azure", "Emerald", "Amber", "Violet", "Coral",
                "Indigo", "Scarlet", "Golden", "Silver", "Bronze", "Ivory", "Jade",
                "Ruby", "Sapphire", "Turquoise", "Magenta", "Lavender", "Maroon",
                "Cerulean", "Olive", "Plum",
            ],
            // prettier-ignore
            [
                "Whale", "Tiger", "Eagle", "Falcon", "Hawk", "Panther", "Jaguar",
                "Leopard", "Lion", "Wolf", "Bear", "Stag", "Lynx", "Orca", "Shark",
                "Heron", "Crane", "Flamingo", "Peacock", "Toucan", "Parrot", "Hare",
                "Deer", "Raven", "Dove", "Swan", "Dolphin", "Cobra", "Fox", "Mantis",
            ],
        ],
    },
    // Docker-style: adjective + scientist
    {
        parts: [
            // prettier-ignore
            [
                "Brave", "Eager", "Curious", "Clever", "Bold", "Wise", "Kind",
                "Gentle", "Quiet", "Humble", "Sharp", "Bright", "Noble", "Serene",
                "Keen", "Jolly", "Elegant", "Focused", "Stoic", "Thoughtful",
            ],
            // prettier-ignore
            [
                "Einstein", "Curie", "Newton", "Darwin", "Tesla", "Hawking",
                "Feynman", "Galileo", "Kepler", "Pasteur", "Hopper", "Turing",
                "Lovelace", "Noether", "Mendel", "Goodall", "Franklin", "Meitner",
                "Bohr", "Euler", "Ramanujan", "Faraday", "Maxwell", "Heisenberg",
                "Dirac", "Fermi", "Sagan", "Rutherford", "Planck", "Volta",
            ],
        ],
    },
    // Mythical: adjective + creature
    {
        parts: [
            // prettier-ignore
            [
                "Ancient", "Mystic", "Shadow", "Golden", "Silent", "Hidden",
                "Enchanted", "Wandering", "Moonlit", "Fabled", "Ethereal", "Arcane",
                "Celestial", "Radiant", "Eternal", "Whispering", "Haunted", "Sacred",
                "Forgotten", "Crystal", "Emerald", "Starlit", "Twilight", "Iron",
                "Storm",
            ],
            // prettier-ignore
            [
                "Phoenix", "Griffin", "Dragon", "Unicorn", "Pegasus", "Kraken",
                "Sphinx", "Chimera", "Hydra", "Basilisk", "Cerberus", "Minotaur",
                "Centaur", "Gorgon", "Siren", "Banshee", "Wraith", "Djinn",
                "Leviathan", "Wyvern", "Roc", "Yeti", "Kelpie", "Kitsune", "Nymph",
                "Sylph", "Faun", "Imp", "Golem", "Valkyrie",
            ],
        ],
    },
    // Nature: adjective + landmark
    {
        parts: [
            // prettier-ignore
            [
                "Quiet", "Wandering", "Misty", "Sunny", "Hidden", "Silent",
                "Distant", "Frozen", "Windy", "Wild", "Emerald", "Golden", "Ancient",
                "Rolling", "Still", "Rugged", "Verdant", "Craggy", "Dewy",
                "Shimmering", "Tranquil", "Lush", "Lonely", "Open", "Secret",
            ],
            // prettier-ignore
            [
                "River", "Mountain", "Valley", "Forest", "Meadow", "Canyon",
                "Glacier", "Waterfall", "Lake", "Ocean", "Desert", "Prairie",
                "Tundra", "Reef", "Cliff", "Lagoon", "Marsh", "Grove", "Ridge",
                "Island", "Cave", "Harbor", "Summit", "Delta", "Oasis", "Fjord",
                "Geyser", "Bay", "Plateau", "Savanna",
            ],
        ],
    },
    // Cosmos: adjective + celestial object
    {
        parts: [
            // prettier-ignore
            [
                "Cosmic", "Distant", "Stellar", "Lunar", "Solar", "Radiant",
                "Nebular", "Orbital", "Galactic", "Celestial", "Drifting", "Glowing",
                "Spinning", "Shooting", "Burning", "Frozen", "Silent", "Ancient",
                "Rogue", "Gleaming", "Whispering", "Falling", "Spiral", "Twinkling",
                "Pulsing",
            ],
            // prettier-ignore
            [
                "Nebula", "Comet", "Asteroid", "Planet", "Star", "Galaxy", "Moon",
                "Sun", "Quasar", "Pulsar", "Meteor", "Orbit", "Eclipse",
                "Constellation", "Supernova", "Cluster", "Nova", "Aurora", "Cosmos",
                "Void", "Horizon", "Satellite", "Crater", "Ring", "Belt", "Cloud",
                "Ray", "Spiral", "Dust", "Atlas",
            ],
        ],
    },
    // Snack: adjective + food
    {
        parts: [
            // prettier-ignore
            [
                "Spicy", "Jolly", "Sweet", "Tangy", "Crispy", "Juicy", "Zesty",
                "Ripe", "Savory", "Fresh", "Hot", "Creamy", "Fluffy", "Fizzy",
                "Chunky", "Toasty", "Buttery", "Sugary", "Salty", "Tasty", "Gooey",
                "Smoky", "Nutty", "Golden", "Flaky",
            ],
            // prettier-ignore
            [
                "Mango", "Biscuit", "Pineapple", "Pancake", "Taco", "Pretzel",
                "Donut", "Waffle", "Burrito", "Muffin", "Noodle", "Dumpling",
                "Pickle", "Croissant", "Bagel", "Cupcake", "Sushi", "Pizza",
                "Pudding", "Cookie", "Brownie", "Fritter", "Crumble", "Scone", "Pie",
                "Pastry", "Eclair", "Cheesecake", "Truffle", "Macaron",
            ],
        ],
    },
];

function pickRandom(list) {
    return list[Math.floor(Math.random() * list.length)];
}

export function randomAnonymousName() {
    const theme = pickRandom(THEMES);
    return theme.parts.map(pickRandom).join(" ");
}
