from pages.Visualization.Stops import plot_stop_activity, stops_from_data, split_and_adjust_duration
from Setup import *
import streamlit as st
import altair as alt


def metric_availability(device, df_stops):

    # Extract the date from 'start_time' to group by
    df_stops['start_date'] = df_stops['start_time'].dt.date

    # Aggregate the downtime for each day
    df_downtime = df_stops.groupby('start_date')['duration'].sum().reset_index()

    # Convert 'start_date' back to datetime object for consistency
    df_downtime['start_date'] = pd.to_datetime(df_downtime['start_date'])
    
    # Generate date range based on min and max dates in df_downtime
    time = device.plot_variables['Time']['Column']
    date = device.data[time].dt.date

    date_range = pd.date_range(start=date.min(), end=date.max(), freq='D')
    
    # Create DataFrame with date_range and initialize planned_production_time to 0
    df_planned = pd.DataFrame({'date': date_range})
    df_planned['planned_production_time'] = 0
    
    # Identify weekdays (0=Monday, 1=Tuesday, ..., 6=Sunday)
    df_planned['weekday'] = df_planned['date'].dt.weekday
    
    # Set planned_production_time to 24*60 minutes for weekdays between Monday and Friday
    day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}
    shift_start_day = st.session_state['shift']['work_days'][0]
    shift_end_day = st.session_state['shift']['work_days'][1]
    start_time = st.session_state['shift']['start_time']
    end_time = st.session_state['shift']['end_time']
    total_time = (end_time.hour * 60 + end_time.minute) - (start_time.hour * 60 + start_time.minute) + 1
    
    df_planned.loc[df_planned['weekday'].between(day_map[shift_start_day], day_map[shift_end_day]), 'planned_production_time'] = total_time
    
    # Merge df_downtime and df_planned on date
    df_final = pd.merge(df_planned, df_downtime, left_on='date', right_on='start_date', how='left')
    
    #remove start_date
    df_final.drop(columns=['start_date'], inplace=True)
    
    # Fill NA values in 'duration' column with 0
    df_final['duration'].fillna(0, inplace=True)
    
    # if stop_time > 1, planned_production_time = total_time
    df_final.loc[df_final['duration'] > 1, 'planned_production_time'] = total_time
    
    # Calculate run_time and availability
    df_final['run_time'] = df_final['planned_production_time'] - df_final['duration']
    df_final['availability'] = df_final['run_time'] / df_final['planned_production_time']
    df_final['availability'].replace(np.inf, 0, inplace=True)  # Replace inf with 0 (for days with 0 planned_production_time)
    
    # if availability is 0 or 1, replace with NaN
    df_final['availability'].replace(0, np.nan, inplace=True)
    df_final['availability'].replace(1, np.nan, inplace=True)  
    
    # if run_time is -1, replace availability with Nan
    df_final.loc[df_final['run_time'] < 0, 'availability'] = np.nan
    
    #rename duration to stop_time
    df_final.rename(columns={'duration': 'stop_time'}, inplace=True)
    
    
    # GROUPED BY WEEK AND MONTH
    
    df_availability_day = df_final.copy()
    
    # if availability is NaN, replace planned_production_time, run_time and stop_time with NaN
    df_availability_day.loc[df_availability_day['availability'].isna(), 'planned_production_time'] = np.nan
    df_availability_day.loc[df_availability_day['availability'].isna(), 'run_time'] = np.nan
    df_availability_day.loc[df_availability_day['availability'].isna(), 'stop_time'] = np.nan
    
    # group per week of year
    df_availability_week = df_availability_day.copy()
    df_availability_week['week'] = df_availability_week['date'].dt.isocalendar().week
    df_availability_week['year'] = df_availability_week['date'].dt.year
    # remove weekday column
    df_availability_week.drop(columns=['weekday', 'date'], inplace=True)
    df_availability_week = df_availability_week.groupby(['year', 'week'], sort=False, as_index=False).mean(numeric_only=False)


    df_availability_month = df_availability_day.copy()
    # group per month-year   
    df_availability_month['month'] = df_availability_month['date'].dt.month
    df_availability_month['year'] = df_availability_month['date'].dt.year
    # remove weekday column
    df_availability_month.drop(columns=['weekday', 'date'], inplace=True)
    df_availability_month = df_availability_month.groupby(['year', 'month'], sort=False, as_index=False).mean(numeric_only=False)
    
    # st.write(df_availability_day)
    # st.write(df_availability_week)
    # st.write(df_availability_month)
    
    return df_availability_day, df_availability_week, df_availability_month

def metric_quality(device):
    
    quality_df = device.metrics['quality_data'].copy() 
    
    product_name = device.metrics['product_variable']
    product_column = device.settings['Categorical'][product_name]['column']
    unique_orders = device.data[product_column].unique()
    quality_df['order'] = quality_df['order'].astype(str)
    
    # filter quality_df by unique_orders
    quality_df = quality_df[quality_df['order'].isin(unique_orders)]
    
    quality_df.loc[quality_df['total_production'] == 0, 'good_production'] = 0
    quality_df['quality'] = quality_df['good_production'] / quality_df['total_production']
    quality_df['goal_ratio'] = quality_df['good_production'] / quality_df['goal']
    
    # if quality > 1, replace with 1
    quality_df.loc[quality_df['quality'] > 1, 'quality'] = 1
    
    # convert date to datetime
    quality_df['start_date'] = pd.to_datetime(quality_df['start_date'])
    quality_df['end_date'] = pd.to_datetime(quality_df['end_date'])
    
    # Group by day
    quality_day_df = quality_df.copy()
    quality_day_df['date'] = quality_day_df['start_date'].dt.date    
    quality_day_df['date'] = pd.to_datetime(quality_day_df['date'])
    quality_day_df.drop(columns=['start_date', 'end_date', 'order'], inplace=True)
    quality_day_df = quality_day_df.groupby(['date'], sort=False, as_index=False).mean(numeric_only=False)
    
    # Group by week
    quality_week_df = quality_df.copy()
    quality_week_df['week'] = quality_week_df['start_date'].dt.isocalendar().week
    quality_week_df['year'] = quality_week_df['start_date'].dt.year
    quality_week_df.drop(columns=['start_date', 'end_date', 'order'], inplace=True)
    quality_week_df = quality_week_df.groupby(['year', 'week'], sort=False, as_index=False).mean(numeric_only=False)
    
    # Group by month
    quality_month_df = quality_df.copy()
    quality_month_df['month'] = quality_month_df['start_date'].dt.month
    quality_month_df['year'] = quality_month_df['start_date'].dt.year
    quality_month_df.drop(columns=['start_date', 'end_date', 'order'], inplace=True)
    quality_month_df = quality_month_df.groupby(['year', 'month'], sort=False, as_index=False).mean(numeric_only=False)
    
    
    # st.write(quality_df)
    # st.write(quality_day_df)
    # st.write(quality_week_df)
    # st.write(quality_month_df)
    
    return quality_df, quality_day_df, quality_week_df, quality_month_df

def sum_stops_for_order(row, df_stops, production_column):
    
    mask = df_stops[production_column] == row['order']
    return df_stops[mask]['duration'].sum()

def metric_performance(device, df_stops):
    
    df_orders = device.metrics['quality_data'].copy() 
    # if total_production is 0, good_production is 0
    df_orders.loc[df_orders['total_production'] == 0, 'good_production'] = 0
    
    production_name = device.metrics['product_variable']
    production_column = device.settings['Categorical'][production_name]['column']
    unique_orders = df_stops[production_column].unique()
    
    #convert df_orders['order'] to string
    df_orders['order'] = df_orders['order'].astype(str)
    
    # filter df_orders by unique_orders
    df_orders = df_orders[df_orders['order'].isin(unique_orders)]
    
    ideal_cycle_time = 60 / device.metrics['baseline'] # in minutes
      
    df_orders['start_date'] = pd.to_datetime(df_orders['start_date'])
    df_orders['end_date'] = pd.to_datetime(df_orders['end_date'])  
      
    # Apply the sum_stops_for_order function and add the result as a new column
    df_orders['total_stop_duration'] = df_orders.apply(lambda row: sum_stops_for_order(row, df_stops, production_column), axis=1)
    df_orders['planned_production_time'] = (df_orders['end_date'] - df_orders['start_date']).dt.total_seconds() / 60 # in minutes
    df_orders['run_time'] = df_orders['planned_production_time'] - df_orders['total_stop_duration']
    
    # Availability = Run Time / Planned Production Time
    df_orders['availability'] = df_orders['run_time'] / df_orders['planned_production_time']
    # availability_order = df_orders.copy()
    
    # df_orders.drop(columns=['availability'], inplace=True)
    
    df_orders['performance'] = (ideal_cycle_time * df_orders['total_production']) / df_orders['run_time']
    
    availability_performace_order = df_orders.copy()
    
    # # Group by day
    # performace_day_df = performace_order.copy()
    # performace_day_df['date'] = performace_day_df['start_date'].dt.date
    # performace_day_df['date'] = pd.to_datetime(performace_day_df['date'])
    # performace_day_df.drop(columns=['start_date', 'end_date', 'order'], inplace=True)
    # performace_day_df = performace_day_df.groupby(['date'], sort=False, as_index=False).mean(numeric_only=False)
    
    # # Group by week
    # performace_week_df = performace_order.copy()
    # performace_week_df['week'] = performace_week_df['start_date'].dt.isocalendar().week
    # performace_week_df['year'] = performace_week_df['start_date'].dt.year
    # performace_week_df.drop(columns=['start_date', 'end_date', 'order'], inplace=True)
    # performace_week_df = performace_week_df.groupby(['year', 'week'], sort=False, as_index=False).mean(numeric_only=False)
    
    # # Group by month
    # performace_month_df = performace_order.copy()
    # performace_month_df['month'] = performace_month_df['start_date'].dt.month
    # performace_month_df['year'] = performace_month_df['start_date'].dt.year
    # performace_month_df.drop(columns=['start_date', 'end_date', 'order'], inplace=True)
    # performace_month_df = performace_month_df.groupby(['year', 'month'], sort=False, as_index=False).mean(numeric_only=False)
    
    
    # st.write(availability_order)
    # st.write(performace_order)
    # st.write(performace_day_df)
    # st.write(performace_week_df)
    # st.write(performace_month_df)
    
    return availability_performace_order

def metric_oee(availability, quality, performance):
        
    availability_order = availability['order'][ ['order', 'availability'] ]
    quality_order = quality['order'][ ['order', 'quality'] ]
    performance_order = performance['order'][ ['order', 'performance'] ]
    df_metrics = pd.merge(availability_order, quality_order, on='order', how='left')
    df_metrics = pd.merge(df_metrics, performance_order, on='order', how='left')
    df_metrics['oee'] = df_metrics['availability'] * df_metrics['quality'] * df_metrics['performance']
    
    availability_day = availability['day'][ ['date', 'availability'] ]
    quality_day = quality['day'][ ['date', 'quality'] ]
    performance_day = performance['day'][ ['date', 'performance'] ]
    
    oee_day = pd.merge(availability_day, quality_day, on='date', how='left')
    oee_day = pd.merge(oee_day, performance_day, on='date', how='left')
    oee_day['oee'] = oee_day['availability'] * oee_day['quality'] * oee_day['performance']
     
    availability_week = availability['week'][ ['year', 'week', 'availability'] ]  
    quality_week = quality['week'][ ['year', 'week', 'quality'] ]
    performance_week = performance['week'][ ['year', 'week', 'performance'] ]
    oee_week = pd.merge(availability_week, quality_week, on=['year', 'week'], how='left')
    oee_week = pd.merge(oee_week, performance_week, on=['year', 'week'], how='left')
    oee_week['oee'] = oee_week['availability'] * oee_week['quality'] * oee_week['performance']
    
    availability_month = availability['month'][ ['year', 'month', 'availability'] ]
    quality_month = quality['month'][ ['year', 'month', 'quality'] ]
    performance_month = performance['month'][ ['year', 'month', 'performance'] ]
    oee_month = pd.merge(availability_month, quality_month, on=['year', 'month'], how='left')
    oee_month = pd.merge(oee_month, performance_month, on=['year', 'month'], how='left')
    oee_month['oee'] = oee_month['availability'] * oee_month['quality'] * oee_month['performance']
    
    oee = {'order': df_metrics, 'day': oee_day, 'week': oee_week, 'month': oee_month}

    
    return oee

def plot_metrics_over_time(df_metrics, metrics):
    
    metric = st.selectbox("Select metric:", ["Availability", "Performance", "Quality", "OEE"], key="metric")
    
    tooltip = [
        {'field': 'start_date', 'type': 'temporal', 'title': 'Date'},
        {'field': 'order', 'type': 'nominal', 'title': 'Order'},
        {'field': metric.lower(), 'type': 'quantitative', 'format': '.1%', 'title': metric},
    ]
    
    if metric == "OEE":
        tooltip.append({'field': 'availability', 'type': 'quantitative', 'format': '.1%', 'title': 'Availability'})
        tooltip.append({'field': 'quality', 'type': 'quantitative', 'format': '.1%', 'title': 'Quality'})
        tooltip.append({'field': 'performance', 'type': 'quantitative', 'format': '.1%', 'title': 'Performance'})
    if metric == "Performance":
        tooltip.append({'field': 'total_production', 'type': 'quantitative', 'format': '.0f', 'title': 'Total Production'})
        tooltip.append({'field': 'run_time', 'type': 'quantitative', 'format': '.0f', 'title': 'Run Time [min]'})
    if metric == "Availability":
        tooltip.append({'field': 'run_time', 'type': 'quantitative', 'format': '.0f', 'title': 'Run Time [min]'})
        tooltip.append({'field': 'planned_production_time', 'type': 'quantitative', 'format': '.0f', 'title': 'Planned Production Time [min]'})
    if metric == "Quality":
        tooltip.append({'field': 'good_production', 'type': 'quantitative', 'format': '.0f', 'title': 'Good Production'})
        tooltip.append({'field': 'total_production', 'type': 'quantitative', 'format': '.0f', 'title': 'Total Production'})
    
    base = alt.Chart(df_metrics).mark_line(point=True).encode(
        x = alt.X('start_date:T', title='Date'),
        y = alt.Y(metric.lower() + ':Q', title='Percentage (%)', axis=alt.Axis(format='%')),
        tooltip=tooltip,
        )
    rule = alt.Chart(df_metrics).mark_rule(color='green').encode(
    y='mean(' + metric.lower() + '):Q'
    )    
    chart = (base + rule).properties(height=250)
        
        
        
    st.altair_chart(chart, use_container_width=True)
    
    col1, col2, col3 = st.columns([1, 1, 3])
    col1.download_button("Download all metrics", data=df_metrics.to_csv(index=False), file_name="metrics.csv", mime="text/csv")
    
    show_table = col2.toggle("Show table", key="show_table", value=False)
    if show_table:
        st.dataframe(df_metrics, use_container_width=True)
    
    return
    
def plot_metrics_grouped(df_metrics, device):
    
    df = device.data.copy()
    df_metrics.drop(columns=['start_date', 'end_date'], inplace=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    groups = device.metrics['family_products']
    groups.append(device.metrics['product_variable'])
    
    groups_columns = []
    for group in groups:
        groups_columns.append(device.settings['Categorical'][group]['column'])
    
    df = df[groups_columns]
    df = df.drop_duplicates(subset=device.settings['Categorical'][device.metrics['product_variable']]['column'])
    df.rename(columns={device.settings['Categorical'][device.metrics['product_variable']]['column']: 'order'}, inplace=True)
    
    df_metrics = pd.merge(df_metrics, df, on='order', how='left')

    group_by = col1.selectbox("Group by:", groups, key="groupby")
    metric = col2.selectbox("Select metric:", ["Availability", "Performance", "Quality", "OEE"], key="metric_grouped")
    sort_by = col3.selectbox("Sort by:", ["Value", "Name"], key="sort")
    order = col4.selectbox("Order:", ["Ascending", "Descending"], key="order")
    
    if sort_by == "Value":
        if order == "Ascending":
            sort = 'x'
        elif order == "Descending":
            sort = '-x'
    elif sort_by == "Name":
        if order == "Ascending":
            sort = 'ascending'
        elif order == "Descending":
            sort = 'descending'
            
    
    
    if group_by != device.metrics['product_variable']:
        df_metrics.drop(columns=['order'], inplace=True)
        df_metrics = df_metrics.groupby(device.settings['Categorical'][group_by]['column'], sort=False, as_index=False).mean(numeric_only=False)
    
    df_metrics['availability'] = df_metrics['run_time'] / df_metrics['planned_production_time']
    df_metrics['quality'] = df_metrics['good_production'] / df_metrics['total_production']
    df_metrics['performance'] = (60 / device.metrics['baseline']) * df_metrics['total_production'] / df_metrics['run_time']
    df_metrics['oee'] = df_metrics['availability'] * df_metrics['quality'] * df_metrics['performance']
    
    # if oee = NaN, replace performance, availability, quality and oee with 0
    df_metrics.loc[df_metrics['oee'].isna(), 'performance'] = 0
    df_metrics.loc[df_metrics['oee'].isna(), 'availability'] = 0
    df_metrics.loc[df_metrics['oee'].isna(), 'quality'] = 0
    df_metrics.loc[df_metrics['oee'].isna(), 'oee'] = 0
    
    if group_by == device.metrics['product_variable']:
        y = 'order'
    else:
        y = device.settings['Categorical'][group_by]['column']
    
    base = alt.Chart(df_metrics).mark_bar().encode(
        x = alt.X(field=metric.lower(), type= 'quantitative', title=metric, axis=alt.Axis(format='%')),
        y = alt.Y(field=y, type='nominal', title=group_by, sort=sort),
    )
    
    text = base.mark_text(
        align='left',
        baseline='middle',
        dx=3  # Nudges text to right so it doesn't appear on top of the bar
    ).encode(  
        text=alt.Text(field=metric.lower(), type= 'quantitative', format='.1%', title=metric)
    )
    
    
    rule = alt.Chart(df_metrics).mark_rule(color='green').encode(
    #x='mean(' + metric.lower() + '):Q'
    x = alt.X('mean(' + metric.lower() + '):Q', title=metric, axis=alt.Axis(format='0.1%')),
    )    
    
    chart = base + text + rule
    
    st.altair_chart(chart, use_container_width=True)
    
    st.download_button("Download grouped metrics", data=df_metrics.to_csv(index=False), file_name="grouped_metrics.csv", mime="text/csv")
    
    df_metrics
    
    return

def metrics(device, plot):
    
    _, stops_dict, _ = stops_from_data(device.plot_variables, device.state_info, device.data, device.settings)
    
    df_stops = pd.DataFrame(stops_dict)
    df_stops = split_and_adjust_duration(df_stops)
    
    stop_name = device.stop_info['stop']
    stop_column = device.settings['Categorical'][stop_name]['column']
    df_stops = df_stops[~df_stops[stop_column].isin(device.metrics['scheduled_stops'])]
    
    quality_order , _ , _ , _= metric_quality(device)
    availability_performace_order = metric_performance(device, df_stops.copy()) 
    
    quality_order = quality_order[['order', 'quality', 'goal_ratio']]
    df_metrics = pd.merge(quality_order, availability_performace_order, on='order', how='left')
    df_metrics['oee'] = df_metrics['availability'] * df_metrics['quality'] * df_metrics['performance']
    
    # if oee = NaN, replace performance, availability, quality and with 0
    df_metrics.loc[df_metrics['oee'].isna(), 'performance'] = 0
    df_metrics.loc[df_metrics['oee'].isna(), 'availability'] = 0
    df_metrics.loc[df_metrics['oee'].isna(), 'quality'] = 0
    df_metrics.loc[df_metrics['oee'].isna(), 'oee'] = 0
    

    # PROBLEM WITH DATA
    # good_production > total_production, total_production = good_production
    df_metrics.loc[df_metrics['good_production'] > df_metrics['total_production'], 'total_production'] = df_metrics['good_production']

    
    availability = df_metrics['run_time'].sum() / df_metrics['planned_production_time'].sum()
    performace = (60 / device.metrics['baseline']) * df_metrics['total_production'].sum() / df_metrics['run_time'].sum()
    quality = df_metrics['good_production'].sum() / df_metrics['total_production'].sum()
    oee = availability * performace * quality
    
    if plot:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(label='Availability', 
                    value= str(round(availability*100, 1)) + '%')
        col2.metric(label='Performance',
                    value= str(round(performace*100, 1)) + '%')
        col3.metric(label='Quality',
                    value= str(round(quality*100, 1)) + '%')
        col4.metric(label='OEE',
                    value= str(round(oee*100, 1)) + '%')
    
        plot_metrics_over_time(df_metrics.copy(), device.metrics)
        plot_metrics_grouped(df_metrics.copy(), device)
    
    return  df_metrics