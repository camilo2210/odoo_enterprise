export async function fetchBankStatementsSourceInto(orm, context) {
    if (!('bank_statements_source' in context) && 'default_journal_id' in context) {
        const [journal] = await orm.read("account.journal", [context.default_journal_id], ["bank_statements_source"]);
        context.bank_statements_source = journal.bank_statements_source;
    }
}
