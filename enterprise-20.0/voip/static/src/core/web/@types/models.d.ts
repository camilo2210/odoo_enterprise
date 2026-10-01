declare module "models" {
    export interface Call {
        abort: () => Promise<void>;
        callDate: Readonly<string>;
        durationString: Readonly<string>;
        end: () => Promise<void>;
        logToChatter: () => Promise<void>;
        miss: () => Promise<void>;
        reject: () => Promise<void>;
        start: () => Promise<void>;
    }
    export interface ResUsersSettings {
        _saveVoipSettings: () => Promise<any>;
        setVoipDoNotDisturb: (minutes: unknown) => void;
    }
    export interface Settings {
        ringtoneOutputDeviceId: string;
    }
}
