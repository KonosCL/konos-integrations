# Buk Connector

Streamlined connector for data synchronization with Odoo.

## Configuration

1. Set your instance

- Go to _Buk > Configuration > Instances_.
- Create a new instance by providing the required parameters.

![image_01.png](static/description/image_01.png)

2. Sync Master Data

- Once the instance is configured, click the **Sync Master Data** button to import Buk account and cost center information.

![image_02.png](static/description/image_02.png)

![image_03.png](static/description/image_03.png)

> [!IMPORTANT]
> Don't forget to associate the respective Odoo's account and analytic account to each imported record.

## How it Works

- Go to _Buk > Data > Periods_.
- Create the period you want to import, then click the **Import period** button.

![image_04.png](static/description/image_04.png)

- This will generate a journal entry that corresponds to the account centralization for the selected period.

![image_05.png](static/description/image_05.png)

> [!WARNING]
> Periods can only be imported once. Be cautious when confirming this action

## Credits

### Authors

- Konos Soluciones & Servicios

### Contributors

- Alexander Olivares <<aolivares@konos.cl>>

### Licence

This module is licensed under [GNU General Public License v3.0](LICENSE).
