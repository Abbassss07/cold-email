-- Index the referencing side of the send_logs -> leads foreign key.
create index send_logs_email_id_idx on public.send_logs(email_id)
where email_id is not null;
