CREATE TABLE channel(
    id varchar,
    name varchar,
    tracked bool,
    PRIMARY KEY(id)
);
CREATE TABLE chan_names(
    id varchar,
    name varchar,
    time_discovered timestamptz,
    PRIMARY KEY (id,name),
    CONSTRAINT chan_id FOREIGN KEY (id) REFERENCES channel(id)
);
CREATE TABLE video(
    video_id varchar,
    channel_id varchar,
    title varchar,
    caught_while varchar,
    live varchar,
    old_title varchar,
    createdDateTime timestamptz,
    publishDateTime timestamptz,
    startedLogAt timestamptz,
    scheduledStartTime timestamptz,
    actualStartTime timestamptz,
    actualEndTime timestamptz,
    retries_of_rerecording integer,
    retries_of_rerecording_had_scs integer,
    PRIMARY KEY (video_id),
    CONSTRAINT chan_id FOREIGN KEY (channel_id) REFERENCES video(video_id)
);
CREATE TABLE messages(
    video_id varchar,
    user_id varchar,
    message_txt varchar,
    time_sent timestamptz,
    currency char(4),
    value numeric(15,6),
    color bigint,
    CONSTRAINT v_id FOREIGN KEY (video_id) REFERENCES video(video_id),
    constraint c_id FOREIGN KEY (user_id) REFERENCES channel(id),
    PRIMARY KEY (video_id,user_id,message_txt,time_sent)
);