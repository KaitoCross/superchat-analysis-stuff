
CREATE DATABASE superchat_data;

CREATE TABLE channel(
    id varchar,
    name varchar,
    tracked bool,
    color char(6),
    PRIMARY KEY(id)
);
CREATE TABLE chan_names(
    id varchar,
    name varchar,
    time_discovered timestamptz,
    time_used timestamptz,
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
    membership bool,
    length bigint,
    createdDateTime timestamptz,
    publishDateTime timestamptz,
    startedLogAt timestamptz,
    endedLogAt timestamptz,
    scheduledStartTime timestamptz,
    actualStartTime timestamptz,
    actualEndTime timestamptz,
    retries_of_rerecording integer,
    retries_of_rerecording_had_scs integer,
    PRIMARY KEY (video_id),
    CONSTRAINT chan_id FOREIGN KEY (channel_id) REFERENCES channel(id)
);
CREATE TABLE messages(
    video_id varchar,
    chat_id varchar,
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

CREATE TABLE area(
    areano int,
    area_name varchar,
    PRIMARY KEY (areano)
);

CREATE TABLE currency(
    code varchar,
    area int,
    PRIMARY KEY(code),
    constraint area_id FOREIGN KEY (area) REFERENCES area(areano)
);

INSERT INTO area VALUES
    (1, 'North America'),(2,'South America'),(3,'Europe'),(4,'Africa'),(5,'Asia'),(6,'Oceania');

INSERT INTO currency(area,code) VALUES
(1,'USD'),(1,'CAD'),(1,'MXN'),
(2,'ARS'),(2,'BOB'),(2,'BRL'),(2,'CLP'),(2,'COP'),(2,'CRC'),(2,'DOP'),(2,'GTQ'),(2,'HNL'),(2,'NIO'),(2,'PEN'),(2,'PYG'),(2,'UYU'),
(3,'BAM'),(3,'BGN'),(3,'BYN'),(3,'CHF'),(3,'CZK'),(3,'DKK'),(3,'EUR'),(3,'GBP'),(3,'HRK'),(3,'HUF'),(3,'ILS'),(3,'ISK'),(3,'NOK'),(3,'PLN'),(3,'RON'),(3,'RSD'),(3,'RUB'),(3,'SEK'),(3,'TRY'),
(4,'ZAR'),(4,'EGP'),(4,'NGN')
(5,'AED'),(5,'HKD'),(5,'INR'),(5,'JOD'),(5,'JPY'),(5,'KRW'),(5,'MYR'),(5,'PHP'),(5,'QAR'),(5,'SAR'),(5,'SGD'),(5,'TWD'),
(6,'AUD'),(6,'NZD');