import { Redirect, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Text } from "react-native";

import { api, ApiError, type Account } from "@/shared/api/client";
import { localDate } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { parseDateInput, parseRubInput } from "@/shared/input";
import { useSession } from "@/shared/session";
import { Button, Card, Choice, ErrorState, Field, Muted, Screen } from "@/shared/ui/components";
import { usePalette } from "@/shared/ui/theme";

type Section = "account" | "obligation" | "income";
type AccountType = "debit" | "cash" | "savings" | "credit_card" | "deposit";
type ObligationKind = "rent" | "loan" | "utilities" | "subscription" | "installment" | "manual";
type IncomeKind = "salary" | "advance" | "freelance" | "other";
type Repeat = "once" | "monthly";

const t = ru.manual;

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : "Неизвестная ошибка.";
}

interface FormProps {
  token: string;
  today: string;
  accounts: Account[];
  onDone: (message: string) => void;
}

function AccountForm({ token, onDone }: FormProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState<AccountType>("debit");
  const [balance, setBalance] = useState("");
  const [limit, setLimit] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const submit = async () => {
    const isCredit = type === "credit_card";
    const parsedBalance = parseRubInput(balance, true);
    const parsedLimit = isCredit ? parseRubInput(limit) : null;
    const next: Record<string, string> = {};
    if (!name.trim()) next.name = t.required;
    if (!parsedBalance.ok) next.balance = parsedBalance.error;
    if (parsedLimit && !parsedLimit.ok) next.limit = parsedLimit.error;
    setErrors(next);
    if (Object.keys(next).length > 0 || !parsedBalance.ok) return;
    setBusy(true);
    setFailure(null);
    try {
      await api.createAccount(token, {
        name: name.trim(),
        type,
        available_balance_minor: parsedBalance.value,
        credit_limit_minor: parsedLimit?.ok ? parsedLimit.value : null,
      });
      setName("");
      setBalance("");
      setLimit("");
      onDone(t.accountSaved);
    } catch (error) {
      setFailure(messageOf(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Field label={t.name} value={name} onChangeText={setName} error={errors.name} />
      <Choice
        label={t.type}
        value={type}
        onChange={setType}
        options={(Object.keys(ru.accountType) as AccountType[]).map((value) => ({
          value,
          label: ru.accountType[value],
        }))}
      />
      <Field
        label={type === "credit_card" ? t.debtHint : t.balance}
        value={balance}
        onChangeText={setBalance}
        keyboardType="numbers-and-punctuation"
        placeholder="12 000,00"
        error={errors.balance}
      />
      {type === "credit_card" ? (
        <Field
          label={t.limit}
          value={limit}
          onChangeText={setLimit}
          keyboardType="decimal-pad"
          error={errors.limit}
          hint={t.limitHint}
        />
      ) : null}
      {failure ? <ErrorState title={t.saveError} message={failure} /> : null}
      <Button label={t.save} onPress={() => void submit()} loading={busy} />
    </>
  );
}

function ObligationForm({ token, today, accounts, onDone }: FormProps) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<ObligationKind>("manual");
  const [amount, setAmount] = useState("");
  const [due, setDue] = useState("");
  const [repeat, setRepeat] = useState<Repeat>("monthly");
  const [accountId, setAccountId] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const submit = async () => {
    const parsedAmount = parseRubInput(amount);
    const parsedDue = parseDateInput(due, today);
    const next: Record<string, string> = {};
    if (!title.trim()) next.title = t.required;
    if (!parsedAmount.ok) next.amount = parsedAmount.error;
    if (!parsedDue.ok) next.due = parsedDue.error;
    setErrors(next);
    if (!parsedAmount.ok || !parsedDue.ok || !title.trim()) return;
    setBusy(true);
    setFailure(null);
    try {
      await api.createObligation(token, {
        title: title.trim(),
        kind,
        amount_minor: parsedAmount.value,
        due_date: parsedDue.value,
        recurrence: repeat === "monthly" ? "monthly" : "none",
        recurrence_day: repeat === "monthly" ? Number(parsedDue.value.slice(8, 10)) : null,
        account_id: accountId,
      });
      setTitle("");
      setAmount("");
      setDue("");
      onDone(t.obligationSaved);
    } catch (error) {
      setFailure(messageOf(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Field label={t.title} value={title} onChangeText={setTitle} error={errors.title} />
      <Choice
        label={t.kind}
        value={kind}
        onChange={setKind}
        options={(Object.keys(t.obligationKinds) as ObligationKind[]).map((value) => ({
          value,
          label: t.obligationKinds[value],
        }))}
      />
      <Field
        label={t.amount}
        value={amount}
        onChangeText={setAmount}
        keyboardType="decimal-pad"
        placeholder="18 000"
        error={errors.amount}
      />
      <Field
        label={t.dueDate}
        value={due}
        onChangeText={setDue}
        placeholder="ДД.ММ или ДД.ММ.ГГГГ"
        error={errors.due}
      />
      <Choice
        label={t.repeat}
        value={repeat}
        onChange={setRepeat}
        options={[
          { value: "monthly", label: t.monthly },
          { value: "once", label: t.once },
        ]}
      />
      {accounts.length > 0 ? (
        <Choice
          label={t.payFrom}
          value={accountId}
          onChange={setAccountId}
          options={accounts.map((a) => ({ value: a.id, label: a.name }))}
        />
      ) : null}
      {failure ? <ErrorState title={t.saveError} message={failure} /> : null}
      <Button label={t.save} onPress={() => void submit()} loading={busy} />
    </>
  );
}

function IncomeForm({ token, today, onDone }: FormProps) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<IncomeKind>("salary");
  const [amount, setAmount] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [repeat, setRepeat] = useState<Repeat>("monthly");
  const [sure, setSure] = useState<"yes" | "no">("yes");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const submit = async () => {
    const parsedAmount = parseRubInput(amount);
    const parsedFrom = parseDateInput(from, today);
    const parsedTo = to.trim() ? parseDateInput(to, today) : null;
    const next: Record<string, string> = {};
    if (!title.trim()) next.title = t.required;
    if (!parsedAmount.ok) next.amount = parsedAmount.error;
    if (!parsedFrom.ok) next.from = parsedFrom.error;
    if (parsedTo && !parsedTo.ok) next.to = parsedTo.error;
    setErrors(next);
    if (!parsedAmount.ok || !parsedFrom.ok || (parsedTo && !parsedTo.ok) || !title.trim()) return;
    setBusy(true);
    setFailure(null);
    try {
      await api.createIncome(token, {
        title: title.trim(),
        kind,
        amount_minor: parsedAmount.value,
        date_from: parsedFrom.value,
        date_to: parsedTo?.ok ? parsedTo.value : null,
        recurrence: repeat === "monthly" ? "monthly" : "none",
        confirmed: sure === "yes",
      });
      setTitle("");
      setAmount("");
      setFrom("");
      setTo("");
      onDone(t.incomeSaved);
    } catch (error) {
      setFailure(messageOf(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Field label={t.title} value={title} onChangeText={setTitle} error={errors.title} />
      <Choice
        label={t.kind}
        value={kind}
        onChange={setKind}
        options={(Object.keys(t.incomeKinds) as IncomeKind[]).map((value) => ({
          value,
          label: t.incomeKinds[value],
        }))}
      />
      <Field
        label={t.amount}
        value={amount}
        onChangeText={setAmount}
        keyboardType="decimal-pad"
        placeholder="60 000"
        error={errors.amount}
      />
      <Field
        label={t.incomeFrom}
        value={from}
        onChangeText={setFrom}
        placeholder="ДД.ММ или ДД.ММ.ГГГГ"
        error={errors.from}
      />
      <Field
        label={t.incomeTo}
        value={to}
        onChangeText={setTo}
        placeholder="ДД.ММ или ДД.ММ.ГГГГ"
        hint={t.incomeToHint}
        error={errors.to}
      />
      <Choice
        label={t.repeat}
        value={repeat}
        onChange={setRepeat}
        options={[
          { value: "monthly", label: t.monthly },
          { value: "once", label: t.once },
        ]}
      />
      <Choice
        label={t.sure}
        value={sure}
        onChange={setSure}
        options={[
          { value: "yes", label: t.sureYes },
          { value: "no", label: t.sureNo },
        ]}
      />
      {failure ? <ErrorState title={t.saveError} message={failure} /> : null}
      <Button label={t.save} onPress={() => void submit()} loading={busy} />
    </>
  );
}

export function AddScreen() {
  const router = useRouter();
  const palette = usePalette();
  const { session } = useSession();
  const token = session?.access_token;
  const [section, setSection] = useState<Section>("obligation");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api
      .listAccounts(token)
      .then((data) => setAccounts(data.items))
      .catch(() => setAccounts([]));
  }, [token, notice]);

  if (!session || !token) {
    return <Redirect href="/" />;
  }
  const asOf = session.data_quality.data_as_of;
  const today = asOf ? localDate(asOf) : new Date().toISOString().slice(0, 10);
  const props: FormProps = { token, today, accounts, onDone: setNotice };

  return (
    <Screen>
      <Card title={t.title_screen}>
        <Muted>{t.lead}</Muted>
        <Choice
          value={section}
          onChange={(value) => {
            setSection(value);
            setNotice(null);
          }}
          options={[
            { value: "obligation", label: t.sections.obligation },
            { value: "income", label: t.sections.income },
            { value: "account", label: t.sections.account },
          ]}
        />
      </Card>
      <Card>
        {section === "account" ? <AccountForm {...props} /> : null}
        {section === "obligation" ? <ObligationForm {...props} /> : null}
        {section === "income" ? <IncomeForm {...props} /> : null}
        {notice ? <Text style={{ color: palette.ok }}>{notice}</Text> : null}
      </Card>
      <Button label={t.toCalendar} variant="secondary" onPress={() => router.push("/calendar")} />
    </Screen>
  );
}
