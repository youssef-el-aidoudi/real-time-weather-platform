{{ config(
    materialized='table',
    unique_key='id'
) }}


SELECT
    id,
    city,
    temperature,
    weather_description,
    wind_speed,
    weather_time_local,
    inserted_at_local
FROM
    {{ ref('stg_weather_data') }}
